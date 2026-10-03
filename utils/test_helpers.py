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


def make_accountant(username="acc_helper"):
    from accounts.models import User
    from core.models import Specialty
    sp, _ = Specialty.objects.get_or_create(name="حسابدار")
    user = User.objects.create_user(username=username, password="pw", role=User.Role.EMPLOYEE)
    user.specialties.add(sp)
    return user
