import os
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.storage import default_storage
from django.db import transaction

from core.capabilities import can
from utils.image_utils import optimize_named
from .models import SavedLocation

TITLE_MAX = 120
DESCRIPTION_MAX = 2000
MAX_IMAGE_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx
IMAGE_EXTS = ("jpg", "jpeg", "png", "webp")
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_QUANT = Decimal("0.000001")


def _require(actor):
    if not can(actor, "locations.manage"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند موقعیت‌ها را مدیریت کند.")


def parse_coordinate(raw, *, limit, label):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN).replace("٫", ".")
    if not text:
        raise ValueError(f"{label} را وارد کنید.")
    if "e" in text.lower():
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    if not value.is_finite() or abs(value) > limit:
        raise ValueError(f"{label} باید بین {-limit} و {limit} باشد.")
    return value.quantize(_QUANT)


def _clean_title(raw):
    title = " ".join(str(raw or "").split())
    if not title:
        raise ValueError("عنوان را بنویسید.")
    if len(title) > TITLE_MAX:
        raise ValueError(f"عنوان نباید بیش از {TITLE_MAX} نویسه باشد.")
    return title


def _clean_description(raw):
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > DESCRIPTION_MAX:
        raise ValueError(f"توضیحات نباید بیش از {DESCRIPTION_MAX} نویسه باشد.")
    return text


def _prepare_image(uploaded):
    """فایل بهینه‌شده با نام تصادفی، یا ValueError فارسی. فقط JPG، PNG و WEBP."""
    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "image"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in IMAGE_EXTS:
        raise ValueError("تصویر باید JPG، PNG یا WEBP باشد.")
    if uploaded.size > MAX_IMAGE_BYTES:
        raise ValueError("حجم تصویر بیشتر از ۲۵ مگابایت است.")
    prepared, name = optimize_named(uploaded, name)   # تصویر جعلی ← ValueError فارسی
    prepared.name = f"{uuid.uuid4().hex}.{name.rsplit('.', 1)[-1].lower()}"
    return prepared


def _delete_after_commit(name):
    if name:
        transaction.on_commit(lambda: default_storage.delete(name))


def _clean_all(title, description, lat_raw, lng_raw, image):
    return (_clean_title(title), _clean_description(description),
            parse_coordinate(lat_raw, limit=90, label="عرض جغرافیایی"),
            parse_coordinate(lng_raw, limit=180, label="طول جغرافیایی"),
            _prepare_image(image) if image else None)


@transaction.atomic
def create_location(*, actor, title, description, lat_raw, lng_raw, image=None):
    _require(actor)
    title, description, lat, lng, prepared = _clean_all(title, description, lat_raw, lng_raw, image)
    place = SavedLocation(title=title, description=description, latitude=lat, longitude=lng, created_by=actor)
    if prepared is not None:
        place.image.save(prepared.name, prepared, save=False)
    place.save()
    return place


@transaction.atomic
def update_location(*, actor, location_id, title, description, lat_raw, lng_raw, image=None, remove_image=False):
    """کد لینک عمومی با ویرایش عوض نمی‌شود. image=None و remove_image=False یعنی تصویر دست نخورد."""
    _require(actor)
    title, description, lat, lng, prepared = _clean_all(title, description, lat_raw, lng_raw, image)
    place = SavedLocation.objects.select_for_update(of=("self",)).filter(pk=location_id).first()
    if place is None:
        raise ValueError("این موقعیت پیدا نشد؛ صفحه را تازه کنید.")
    old = place.image.name
    place.title, place.description, place.latitude, place.longitude = title, description, lat, lng
    if prepared is not None:
        place.image.save(prepared.name, prepared, save=False)
        _delete_after_commit(old)
    elif remove_image and old:
        place.image = ""
        _delete_after_commit(old)
    place.save()
    return place


@transaction.atomic
def delete_location(*, actor, location_id):
    _require(actor)
    place = SavedLocation.objects.select_for_update(of=("self",)).filter(pk=location_id).first()
    if place is None:
        raise ValueError("این موقعیت پیدا نشد؛ صفحه را تازه کنید.")
    _delete_after_commit(place.image.name)
    place.delete()
