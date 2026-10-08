import os
from datetime import timedelta
from io import BytesIO

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageOps

from utils.image_utils import optimize_image, optimize_named

from .models import Attachment

MAX_FILES = 10
MAX_BYTES = 24 * 1024 * 1024          # nginx ۲۵ مگابایت است؛ یک مگابایت جا برای فیلدهای فرم
MAX_VOICE_SECONDS = 300
UPLOAD_LIMIT, UPLOAD_WINDOW = 40, 60  # حداکثر ۴۰ آپلود در دقیقه برای هر کاربر
ORPHAN_HOURS = 24
THUMB_SIDE = 480

IMAGE_EXT = {"jpg", "jpeg", "png", "webp", "gif", "bmp"}
VIDEO_EXT = {"mp4", "webm", "mov", "m4v"}
AUDIO_EXT = {"mp3", "m4a", "ogg", "opus", "wav", "aac"}
VOICE_EXT = AUDIO_EXT | {"webm", "mp4"}
LABELS = {"image": "عکس", "video": "ویدیو", "audio": "فایل صوتی", "voice": "پیام صوتی", "file": "فایل"}
_BAD_IMAGE = (OSError, SyntaxError, EOFError, ValueError, Image.DecompressionBombError)

AVATAR_EXT = {"jpg", "jpeg", "png", "webp", "bmp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_PIXELS = 40_000_000


def ext_of(name):
    return os.path.splitext(name or "")[1].lower().lstrip(".")


def kind_for(name, voice=False):
    ext = ext_of(name)
    if voice and ext in VOICE_EXT:
        return Attachment.Kind.VOICE
    if ext in IMAGE_EXT:
        return Attachment.Kind.IMAGE
    if ext in VIDEO_EXT:
        return Attachment.Kind.VIDEO
    if ext in AUDIO_EXT:
        return Attachment.Kind.AUDIO
    return Attachment.Kind.FILE


def media_url(rel):
    return reverse("protected_media", kwargs={"path": rel})


def serialize_attachment(a):
    return {
        "id": a.id, "kind": a.kind, "name": a.original_name, "size": a.size,
        "url": media_url(a.file.name), "thumb": media_url(a.thumb.name) if a.thumb else "",
        "w": a.width, "h": a.height, "dur": a.duration,
    }


def label_for(attachments):
    items = list(attachments)
    if not items:
        return ""
    return "آلبوم" if len(items) > 1 else LABELS.get(items[0].kind, "فایل")


def clean_ids(raw):
    if raw is None or raw == "":
        return []
    parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
    ids = []
    for p in parts:
        p = str(p).strip()
        if not p:
            continue
        if not p.isdigit():
            raise ValueError("شناسه‌ی فایل نامعتبر است.")
        if int(p) not in ids:
            ids.append(int(p))
    if len(ids) > MAX_FILES:
        raise ValueError("در هر پیام حداکثر ۱۰ فایل می‌توان فرستاد.")
    return ids


def _rate(user):
    key = f"msgr:up:{user.pk}"
    cache.add(key, 0, UPLOAD_WINDOW)
    if cache.incr(key) > UPLOAD_LIMIT:
        raise ValueError("تعداد آپلودها در یک دقیقه زیاد است؛ کمی صبر کنید.")


def _image_info(f):
    """(عرض، ارتفاع، thumb یا None). فایل خراب ← ValueError فارسی."""
    try:
        f.seek(0)
        img = Image.open(f)
        img.load()
        w, h = img.size
        thumb = None
        if max(w, h) > THUMB_SIDE and (img.format or "").upper() != "GIF":
            t = ImageOps.exif_transpose(img)
            if t.mode in ("RGBA", "LA", "P"):
                t = t.convert("RGBA")
                bg = Image.new("RGB", t.size, (255, 255, 255))
                bg.paste(t, mask=t.getchannel("A"))
                t = bg
            else:
                t = t.convert("RGB")
            t.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.LANCZOS)
            buf = BytesIO()
            t.save(buf, format="WEBP", quality=75, method=4)
            thumb = ContentFile(buf.getvalue(), name="t.webp")
        f.seek(0)
        return w, h, thumb
    except _BAD_IMAGE:
        raise ValueError("فایل بارگذاری‌شده تصویر معتبری نیست.")


def delete_attachment(a):
    a.file.delete(save=False)
    if a.thumb:
        a.thumb.delete(save=False)
    a.delete()


def cleanup_orphans():
    cutoff = timezone.now() - timedelta(hours=ORPHAN_HOURS)
    for a in list(Attachment.objects.filter(message__isnull=True, created_at__lt=cutoff)[:50]):
        delete_attachment(a)


def delete_for_message(message):
    for a in list(message.attachments.all()):
        delete_attachment(a)


def save_upload(user, conv, uploaded, *, voice=False, duration=None):
    """آپلود یک فایل به‌صورت پیوست یتیم. عضویت و اجازه‌ی ارسال را فراخوان چک کرده است."""
    _rate(user)
    if uploaded is None:
        raise ValueError("فایلی ارسال نشد.")
    if uploaded.size > MAX_BYTES:
        raise ValueError("حجم فایل بیشتر از ۲۴ مگابایت است.")
    name = os.path.basename((uploaded.name or "").replace("\\", "/")).strip()[:255] or "file"
    kind = kind_for(name, voice)
    dur = w = h = thumb = None
    if kind == Attachment.Kind.VOICE:
        try:
            dur = int(duration)
        except (TypeError, ValueError):
            dur = 1
        dur = max(1, min(dur, MAX_VOICE_SECONDS))
    if kind == Attachment.Kind.IMAGE:
        uploaded, name = optimize_named(uploaded, name)
        w, h, thumb = _image_info(uploaded)
    cleanup_orphans()
    att = Attachment(conversation=conv, uploader=user, kind=kind, original_name=name,
                     size=uploaded.size, width=w, height=h, duration=dur)
    att.file.save(name, uploaded, save=False)
    if thumb is not None:
        att.thumb.save("t.webp", thumb, save=False)
    att.save()
    return att


def attach(user, conv, message, ids):
    """پیوست‌های یتیمِ خودِ کاربر در همین گفت‌وگو را به پیام می‌چسباند (به ترتیب ids)."""
    if not ids:
        return
    found = {a.pk: a for a in Attachment.objects.filter(
        pk__in=ids, uploader=user, conversation=conv, message__isnull=True)}
    if len(found) != len(ids):
        raise ValueError("یکی از فایل‌ها پیدا نشد؛ دوباره بارگذاری کنید.")
    if len(ids) > 1 and any(a.kind == Attachment.Kind.VOICE for a in found.values()):
        raise ValueError("پیام صوتی را جدا بفرستید.")
    for order, pk in enumerate(ids):
        done = Attachment.objects.filter(pk=pk, message__isnull=True).update(message=message, order=order)
        if done != 1:
            raise ValueError("یکی از فایل‌ها قبلاً استفاده شده است.")


def prepare_avatar(uploaded):
    """عکس پروفایل ← ContentFile مربع ۵۱۲ با فرمت webp؛ فایل خراب ← ValueError فارسی."""
    bad = "فایل بارگذاری‌شده تصویر معتبری نیست."
    if uploaded is None:
        raise ValueError("عکسی انتخاب نشده است.")
    if uploaded.size > MAX_AVATAR_BYTES:
        raise ValueError("حجم عکس بیشتر از ۵ مگابایت است.")
    if ext_of(uploaded.name) not in AVATAR_EXT:
        raise ValueError("فرمت عکس مجاز نیست؛ JPG، PNG یا WEBP بفرستید.")
    try:
        uploaded.seek(0)
        probe = Image.open(uploaded)
        pixels = probe.width * probe.height
    except _BAD_IMAGE:
        raise ValueError(bad)
    if pixels > MAX_AVATAR_PIXELS:
        raise ValueError("ابعاد عکس بیش از حد بزرگ است.")
    try:
        uploaded.seek(0)
        out = optimize_image(uploaded, profile_name="avatar")
        out.seek(0)
        data = out.read()
        Image.open(BytesIO(data)).verify()
    except _BAD_IMAGE:
        raise ValueError(bad)
    return ContentFile(data, name="avatar.webp")
