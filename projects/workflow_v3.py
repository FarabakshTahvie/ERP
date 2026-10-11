from core.models import Specialty
from .models import ProjectStage, StageKind, WorkflowStepTemplate, WorkflowTemplate

TEMPLATE_NAME = "گردش‌کار v3"
LEGACY_V2_NAME = "گردش‌کار v2"
VISITOR_SPECIALTY_NAME = "بازدیدکننده"
ACCOUNTANT_SPECIALTY_NAME = "حسابدار"
A = WorkflowStepTemplate.ApprovalBy

STEPS = [
    dict(title="بازدید کارگاهی", client_label="بازدید و اندازه‌گیری", kind=StageKind.VISIT,
         specialty=VISITOR_SPECIALTY_NAME, estimated_duration_hours=4),
    dict(title="صدور پیش‌فاکتور", client_label="صدور پیش‌فاکتور", kind=StageKind.PROFORMA,
         specialty=ACCOUNTANT_SPECIALTY_NAME, estimated_duration_hours=4),
    dict(title="تایید پیش‌فاکتور و انتخاب روش پرداخت", client_label="تایید پیش‌فاکتور",
         approval_by=A.CHOOSE_AT_RUNTIME, requires_payment_selection=True),
    dict(title="طراحی اولیه اتوکد", client_label="طراحی اولیه", kind=StageKind.DESIGN_INITIAL,
         specialty="طراح اتوکد", allows_file_upload=True, estimated_duration_hours=8),
    dict(title="تکمیل طراحی", client_label="طراحی نهایی", specialty="طراح اتوکد",
         allows_file_upload=True, estimated_duration_hours=8),
    dict(title="جی‌کدگیری", client_label="آماده‌سازی برش (جی‌کدگیری)", kind=StageKind.GCODE,
         specialty="اپراتور CNC", allows_file_upload=True, estimated_duration_hours=8),
    dict(title="برش‌کاری", client_label="برش", kind=StageKind.CUTTING, specialty="کانال‌کش",
         estimated_duration_hours=8),
    dict(title="مونتاژ", client_label="مونتاژ", specialty="مونتاژکار", estimated_duration_hours=8),
    dict(title="ارسال", client_label="ارسال به محل نصب", kind=StageKind.SHIPPING, specialty="راننده",
         estimated_duration_hours=4),
    dict(title="نصب", client_label="نصب نهایی", kind=StageKind.INSTALL, specialty="نصاب",
         estimated_duration_hours=8),
    dict(title="بازبینی نهایی", client_label="بازبینی نهایی", kind=StageKind.FINAL_REVIEW,
         specialty=ACCOUNTANT_SPECIALTY_NAME, client_visible=False),
]

BASE = dict(kind=StageKind.GENERIC, assign_to_project_creator=False, approval_by=A.NONE,
            requires_payment_selection=False, allows_file_upload=False, client_visible=True,
            estimated_duration_hours=None, client_label="", on_reject_go_to=None)


def build_workflow_v3(*, make_default=False):
    """idempotent: اجرای دوباره، مراحل قالب را طبق STEPS به‌روز می‌کند. خروجی: (template, created)"""
    template, created = WorkflowTemplate.objects.get_or_create(name=TEMPLATE_NAME)
    for order, spec in enumerate(STEPS, start=1):
        spec = dict(spec)
        name = spec.pop("specialty", None)
        specialty = Specialty.objects.get_or_create(name=name)[0] if name else None
        WorkflowStepTemplate.objects.update_or_create(
            template=template, order=order, defaults={**BASE, "responsible_specialty": specialty, **spec})
    if make_default:
        WorkflowTemplate.objects.exclude(pk=template.pk).update(is_default=False)
        template.is_default = True
        template.save(update_fields=["is_default"])
    return template, created


def drop_unused_v2():
    """قالب v2 را فقط وقتی هیچ پروژه یا مرحله‌ای به آن وصل نیست پاک می‌کند. خروجی: True اگر پاک شد."""
    old = WorkflowTemplate.objects.filter(name=LEGACY_V2_NAME).first()
    if old is None:
        return False
    if old.projects.exists() or ProjectStage.objects.filter(step_template__template=old).exists():
        return False
    old.delete()
    return True
