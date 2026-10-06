from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile

IMAGE_PROFILES = {
    "avatar": {"max_size": (512, 512), "format": "WEBP", "quality": 82, "crop_square": True},
    "default": {"max_size": (1920, 1920), "format": "WEBP", "quality": 80, "crop_square": False},
}


def optimize_image(django_file, profile_name="default"):
    profile = IMAGE_PROFILES.get(profile_name, IMAGE_PROFILES["default"])
    django_file.seek(0)
    image = Image.open(django_file)
    image_format = (image.format or "").upper()

    already_optimized = (
        image.width <= profile["max_size"][0]
        and image.height <= profile["max_size"][1]
        and image_format == profile["format"]
    )
    if already_optimized:
        django_file.seek(0)
        return django_file

    image = ImageOps.exif_transpose(image)

    if profile.get("crop_square"):
        side = min(image.size)
        left, top = (image.width - side) // 2, (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))

    image.thumbnail(profile["max_size"], Image.LANCZOS)

    buffer = BytesIO()
    image.convert("RGB").save(buffer, format=profile["format"], quality=profile["quality"], optimize=True)
    buffer.seek(0)

    original_name = getattr(django_file, "name", "image")
    new_name = original_name.rsplit(".", 1)[0] + f".{profile['format'].lower()}"
    return ContentFile(buffer.read(), name=new_name)


MAX_SIDE, MAX_PIXELS = 2400, 80_000_000
QUALITY_LADDER, TARGET_BYTES = (85, 78, 70), 700 * 1024
MIN_GAIN, SKIP_BELOW = 0.9, 120 * 1024
OPTIMIZABLE_EXT = ("jpg", "jpeg", "png", "webp", "bmp")   # heic/gif/svg دست‌نخورده می‌مانند


def _sensitive_exif(image):
    try:
        exif = image.getexif()
        return exif.get(0x0112, 1) != 1 or bool(exif.get_ifd(0x8825))   # چرخش یا GPS
    except Exception:
        return False


def optimize_upload(django_file):
    """خروجی: (فایل، تغییر_کرد؟). فایل نامعتبر ← ValueError فارسی."""
    original_size = django_file.size
    django_file.seek(0)
    try:
        image = Image.open(django_file)
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("ابعاد تصویر بیش از حد بزرگ است.")
        fmt = (image.format or "").upper()
        if getattr(image, "is_animated", False):
            django_file.seek(0)
            return django_file, False
        sensitive = _sensitive_exif(image)
        if fmt == "WEBP" and max(image.size) <= MAX_SIDE and original_size <= SKIP_BELOW and not sensitive:
            django_file.seek(0)
            return django_file, False                    # از قبل بهینه
        if fmt == "JPEG":
            image.draft("RGB", (MAX_SIDE, MAX_SIDE))     # رمزگشایی کم‌حافظه
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("فایل بارگذاری‌شده تصویر معتبری نیست.")

    image = ImageOps.exif_transpose(image)
    resized = max(image.size) > MAX_SIDE
    if resized:
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    has_alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    if has_alpha:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")

    data = b""
    for q in QUALITY_LADDER:                              # کیفیت از بالا؛ فقط تا رسیدن به حجم هدف پایین می‌آید
        buf = BytesIO()
        image.save(buf, format="WEBP", quality=q, method=6)
        data = buf.getvalue()
        if len(data) <= TARGET_BYTES:
            break
    if not (resized or sensitive or has_alpha) and len(data) > original_size * MIN_GAIN:
        django_file.seek(0)
        return django_file, False                         # سود کمتر از ۱۰٪: دوباره‌فشرده‌سازی نمی‌کنیم
    return ContentFile(data, name="image.webp"), True


RECEIPT_MAX_SIDE = MAX_SIDE
RECEIPT_QUALITY = 85
RECEIPT_MAX_PIXELS = MAX_PIXELS
optimize_receipt_image = optimize_upload

