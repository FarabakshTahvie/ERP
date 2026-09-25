from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile


def make_image_file(name="receipt.png", size=(80, 60), fmt="PNG", exif_orientation=None):
    """
    مساعد تست برای ساخت تصویر ساختگی واقعی با Pillow.
    """
    img = Image.new("RGB", size, color=(200, 200, 200))
    buffer = BytesIO()
    kwargs = {}
    if exif_orientation is not None:
        exif = img.getexif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif
    img.save(buffer, format=fmt, **kwargs)
    content = buffer.getvalue()
    content_type = f"image/{fmt.lower()}"
    return SimpleUploadedFile(name, content, content_type=content_type)
