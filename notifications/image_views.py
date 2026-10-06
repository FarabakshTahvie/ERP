import re
import os
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse, Http404, FileResponse

IMAGE_PATTERN = re.compile(r"^[0-9a-f]{32}\.(webp|png|jpg)$")

def public_broadcast_image(request, name):
    """
    نمایش عکس عمومی اعلان همگانی (بدون نیاز به لاگین) برای دریافت توسط نجوا.
    فقط نام با الگوی ^[0-9a-f]{32}\\.(webp|png|jpg)$ و فقط از media/broadcast/ مجاز است.
    هرگونه دسترسی خارج از محدوده یا نام نامعتبر به ۴۰۴ ختم می‌شود.
    """
    if not IMAGE_PATTERN.match(name):
        raise Http404("تصویر نامعتبر است.")

    base_media_dir = Path(settings.MEDIA_ROOT).resolve()
    broadcast_dir = (base_media_dir / "broadcast").resolve()
    target_path = (broadcast_dir / name).resolve()

    # جلوگیری قطعی از path traversal
    try:
        target_path.relative_to(broadcast_dir)
    except ValueError:
        raise Http404("دسترسی غیرمجاز.")

    if not target_path.is_file():
        raise Http404("تصویر یافت نشد.")

    # تعیین Content-Type مناسب
    ext = target_path.suffix.lower()
    content_types = {
        ".webp": "image/webp",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }
    content_type = content_types.get(ext, "application/octet-stream")

    return FileResponse(open(target_path, "rb"), content_type=content_type)
