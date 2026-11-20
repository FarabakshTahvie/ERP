import logging
import os
import re
import secrets
import uuid

from django.db import transaction
from django.db.models import Sum

from core.capabilities import can
from utils.jalali import to_fa_digits
from utils.media_views import _content_type
from . import storage
from .models import ManagedFile

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 24 * 1024 * 1024
TOTAL_LIMIT_BYTES = 4_800_000_000   # ۴٫۸ گیگابایت از ۵ گیگابایت
NAME_MAX = 255
CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
CODE_LENGTH = 10


def _require(actor):
    if not can(actor, "files.manage"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند فایل‌ها را مدیریت کند.")


def size_text(n):
    n = int(n)
    if n >= 1024 ** 3:
        value, unit = n / 1024 ** 3, "گیگابایت"
    elif n >= 1024 ** 2:
        value, unit = n / 1024 ** 2, "مگابایت"
    elif n >= 1024:
        value, unit = n / 1024, "کیلوبایت"
    else:
        return to_fa_digits(f"{n} بایت")
    return to_fa_digits(f"{value:.1f}".rstrip("0").rstrip(".") + f" {unit}")


def icon_for(name):
    ctype = _content_type(name)
    if ctype.startswith("image/"):
        return "image"
    if ctype.startswith(("audio/", "video/")):
        return "play"
    if ctype == "application/pdf":
        return "file-text"
    return "paperclip"


def clean_name(raw):
    text = os.path.basename(str(raw or "").replace("\\", "/"))
    text = "".join(c for c in text if c.isprintable()).strip()
    if len(text) > NAME_MAX:
        base, ext = os.path.splitext(text)
        text = (base[:NAME_MAX - len(ext)] + ext) if len(ext) <= 20 else text[:NAME_MAX]
    return text or "file"


def used_bytes():
    return ManagedFile.objects.aggregate(t=Sum("size"))["t"] or 0


def _new_key(name):
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    ext = f".{ext}" if re.fullmatch(r"[a-z0-9]{1,10}", ext.lstrip(".")) else ""
    return f"filemanager/{uuid.uuid4().hex}{ext}"


def _free_code():
    for _ in range(20):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not ManagedFile.objects.filter(code=code).exists():
            return code
    raise ValueError("ساخت لینک کوتاه انجام نشد؛ دوباره تلاش کنید.")


def upload_file(*, actor, uploaded):
    _require(actor)
    if uploaded is None:
        raise ValueError("فایلی ارسال نشده است.")
    name = clean_name(uploaded.name)
    size = uploaded.size
    if size <= 0:
        raise ValueError(f"«{name}» خالی است.")
    if size > MAX_FILE_BYTES:
        raise ValueError(f"حجم «{name}» بیشتر از {size_text(MAX_FILE_BYTES)} است.")
    if used_bytes() + size > TOTAL_LIMIT_BYTES:
        raise ValueError("فضای فایل‌منیجر پر شده است؛ چند فایل را حذف کنید.")
    key = _new_key(name)
    storage.put(key, uploaded)
    try:
        return ManagedFile.objects.create(name=name, key=key, size=size, code=_free_code(), uploaded_by=actor)
    except Exception:
        try:
            storage.delete(key)   # ثبت در دیتابیس نشد؛ فایل یتیم در ابر نماند
        except storage.StorageError:
            logger.exception("orphan object left in cloud: %s", key)
        raise


@transaction.atomic
def set_public(*, actor, file_id, public):
    """صریح و idempotent (نه toggle)."""
    _require(actor)
    obj = ManagedFile.objects.select_for_update(of=("self",)).filter(pk=file_id).first()
    if obj is None:
        raise ValueError("این فایل پیدا نشد؛ صفحه را تازه کنید.")
    public = bool(public)
    if obj.is_public != public:
        obj.is_public = public
        obj.save(update_fields=["is_public", "updated_at"])
    return obj


@transaction.atomic
def delete_file(*, actor, file_id):
    """اول از ابر پاک می‌شود؛ اگر ابر خطا داد ردیف می‌ماند و کاربر می‌تواند دوباره تلاش کند."""
    _require(actor)
    obj = ManagedFile.objects.select_for_update(of=("self",)).filter(pk=file_id).first()
    if obj is None:
        raise ValueError("این فایل پیدا نشد؛ صفحه را تازه کنید.")
    storage.delete(obj.key)
    obj.delete()
