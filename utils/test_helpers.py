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


def confirm_invoice(invoice):
    """مرحله‌ی «تایید پیش‌فاکتور» پروژه را انجام‌شده می‌کند تا فاکتور بدهی‌ساز شود."""
    from projects.models import ProjectStage, WorkflowStepTemplate, WorkflowTemplate
    project = invoice.project
    tpl = WorkflowTemplate.objects.create(name=f"قالب تایید {project.pk}")
    step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="تایید", requires_payment_selection=True)
    return ProjectStage.objects.create(project=project, step_template=step, order=90, title="تایید",
                                       status=ProjectStage.Status.DONE)
