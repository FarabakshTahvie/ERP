import os
import uuid
from io import BytesIO

from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from core.capabilities import can
from utils.image_utils import optimize_named
from .models import CatalogMedia, Item, Service

MAX_MEDIA = 40
MAX_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx
MAX_DESCRIPTION = 20000
THUMB_SIDE = 480
IMAGE_EXTS = ("jpg", "jpeg", "png", "webp", "gif")
VIDEO_EXTS = ("mp4", "webm", "mov", "m4v")


def get_owner(kind, obj_id):
    model = {"service": Service, "item": Item}.get(kind)
    return model.objects.filter(pk=obj_id).first() if model else None


def media_map(owner):
    """{id: {kind, url, name}} برای رندر مارک‌داون."""
    return {m.pk: {"kind": m.kind, "url": m.file.url, "name": m.original_name} for m in owner.media.all()}


def _guard(actor):
    if not can(actor, "catalog.edit"):
        raise ValueError("فقط مدیر می‌تواند محتوای ویترین را تغییر دهد.")


def _owner_or_error(kind, obj_id):
    owner = get_owner(kind, obj_id)
    if owner is None:
        raise ValueError("این مورد پیدا نشد.")
    return owner


def _clean_name(uploaded):
    return os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "file"


def _ext(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _verify_image(f):
    try:
        f.seek(0)
        Image.open(f).verify()
    except Exception:
        raise ValueError("فایل تصویر معتبر نیست.")
    finally:
        f.seek(0)


def _video_ok(ext, head):
    if ext == "webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"
    return ext in ("mp4", "mov", "m4v") and head[4:8] == b"ftyp"


def _make_thumb(f):
    f.seek(0)
    img = ImageOps.exif_transpose(Image.open(f))
    img.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.LANCZOS)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        img = flat
    else:
        img = img.convert("RGB")
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=78, method=6)
    f.seek(0)
    return ContentFile(buf.getvalue())


def _delete_files_after_commit(names):
    names = [n for n in names if n]
    transaction.on_commit(lambda: [default_storage.delete(n) for n in names])


@transaction.atomic
def update_content(*, kind, obj_id, show, description, actor):
    _guard(actor)
    owner = _owner_or_error(kind, obj_id)
    text = (description or "").replace("\r\n", "\n").strip()
    if len(text) > MAX_DESCRIPTION:
        raise ValueError("متن بیش از حد طولانی است (حداکثر ۲۰٬۰۰۰ نویسه).")
    owner.show_to_clients, owner.description = bool(show), text
    owner.save(update_fields=["show_to_clients", "description", "updated_at"])
    return owner


@transaction.atomic
def set_cover(*, kind, obj_id, uploaded, actor):
    _guard(actor)
    owner = _owner_or_error(kind, obj_id)
    if uploaded is None:
        raise ValueError("فایلی ارسال نشده است.")
    name = _clean_name(uploaded)
    if uploaded.size > MAX_BYTES:
        raise ValueError(f"حجم «{name}» بیشتر از ۲۵ مگابایت است.")
    if _ext(name) not in IMAGE_EXTS:
        raise ValueError("عکس شاخص باید JPG، PNG، WEBP یا GIF باشد.")
    full, name = optimize_named(uploaded, name)
    _verify_image(full)
    thumb = _make_thumb(full)
    old = [owner.cover.name, owner.cover_thumb.name]
    owner.cover.save(f"{uuid.uuid4().hex}.{_ext(name)}", full, save=False)
    owner.cover_thumb.save(f"{uuid.uuid4().hex}.webp", thumb, save=False)
    owner.save(update_fields=["cover", "cover_thumb", "updated_at"])
    _delete_files_after_commit(old)
    return owner


@transaction.atomic
def remove_cover(*, kind, obj_id, actor):
    _guard(actor)
    owner = _owner_or_error(kind, obj_id)
    old = [owner.cover.name, owner.cover_thumb.name]
    owner.cover, owner.cover_thumb = None, None
    owner.save(update_fields=["cover", "cover_thumb", "updated_at"])
    _delete_files_after_commit(old)
    return owner


@transaction.atomic
def add_media(*, kind, obj_id, uploaded, actor):
    _guard(actor)
    owner = _owner_or_error(kind, obj_id)
    if uploaded is None:
        raise ValueError("فایلی ارسال نشده است.")
    name = _clean_name(uploaded)
    if uploaded.size > MAX_BYTES:
        raise ValueError(f"حجم «{name}» بیشتر از ۲۵ مگابایت است.")
    if owner.media.count() >= MAX_MEDIA:
        raise ValueError(f"حداکثر {MAX_MEDIA} فایل برای هر مورد مجاز است.")
    ext = _ext(name)
    if ext in IMAGE_EXTS:
        uploaded, name = optimize_named(uploaded, name)   # عکس جعلی ← ValueError فارسی
        _verify_image(uploaded)
        media_kind = CatalogMedia.Kind.IMAGE
    elif ext in VIDEO_EXTS:
        head = uploaded.read(12)
        uploaded.seek(0)
        if not _video_ok(ext, head):
            raise ValueError("فایل ویدیو معتبر نیست.")
        media_kind = CatalogMedia.Kind.VIDEO
    else:
        raise ValueError("فقط عکس (JPG، PNG، WEBP، GIF) و ویدیو (MP4، WEBM، MOV) مجاز است.")
    uploaded.name = f"{uuid.uuid4().hex}.{_ext(name)}"
    return CatalogMedia.objects.create(**{kind: owner}, kind=media_kind, file=uploaded,
                                       original_name=name, uploaded_by=actor)


@transaction.atomic
def delete_media(*, media, actor):
    """خروجی: (kind, obj_id) صاحب رسانه برای بازگشت به صفحه‌اش."""
    _guard(actor)
    owner = ("service", media.service_id) if media.service_id else ("item", media.item_id)
    _delete_files_after_commit([media.file.name])
    media.delete()
    return owner
