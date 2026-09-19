from io import BytesIO
from PIL import Image
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
