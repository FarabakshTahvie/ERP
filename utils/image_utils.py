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


RECEIPT_MAX_SIDE = 2400      # اسکرین‌شات‌های بانک (~۱۰۸۰×۲۴۰۰) دست‌نخورده می‌مانند
RECEIPT_QUALITY = 85         # برای خوانایی متن رسید کافی است
RECEIPT_MAX_PIXELS = 80_000_000


def optimize_receipt_image(django_file):
    """
    بهینه‌سازی هوشمند تصویر رسید. خروجی: (فایل، تغییر_کرد؟).
    - چرخش EXIF اعمال و EXIF (از جمله GPS) حذف می‌شود.
    - فقط اگر ضلع بزرگ‌تر از سقف باشد کوچک می‌شود (هرگز بزرگ نمی‌شود).
    - خروجی WebP؛ اگر تغییر ابعادی لازم نبود و خروجی بزرگ‌تر از اصل شد، همان فایل اصلی برمی‌گردد.
    - فایلی که تصویر معتبر نباشد ValueError می‌دهد.
    """
    original_size = django_file.size
    django_file.seek(0)
    try:
        image = Image.open(django_file)
        if image.width * image.height > RECEIPT_MAX_PIXELS:
            raise ValueError("ابعاد تصویر بیش از حد بزرگ است.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("فایل بارگذاری‌شده تصویر معتبری نیست.")

    image = ImageOps.exif_transpose(image)
    resized = max(image.size) > RECEIPT_MAX_SIDE
    if resized:
        image.thumbnail((RECEIPT_MAX_SIDE, RECEIPT_MAX_SIDE), Image.LANCZOS)

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=RECEIPT_QUALITY, method=6)
    data = buffer.getvalue()
    if not resized and len(data) >= original_size:
        django_file.seek(0)
        return django_file, False
    return ContentFile(data, name="receipt.webp"), True

