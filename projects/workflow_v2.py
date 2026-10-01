from core.models import Specialty
from .models import WorkflowTemplate, WorkflowStepTemplate, StageKind

TEMPLATE_NAME = "گردش‌کار v2"
VISITOR_SPECIALTY_NAME = "بازدیدکننده"
A = WorkflowStepTemplate.ApprovalBy

STEPS = [
    dict(title="بازدید کارگاهی", client_label="بازدید و اندازه‌گیری", kind=StageKind.VISIT,
         specialty=VISITOR_SPECIALTY_NAME, estimated_duration_hours=4),
    dict(title="صدور پیش‌فاکتور", client_label="صدور پیش‌فاکتور", kind=StageKind.PROFORMA,
         assign_to_project_creator=True, estimated_duration_hours=4),
    dict(title="تایید پیش‌فاکتور و انتخاب روش پرداخت", client_label="تایید پیش‌فاکتور",
         approval_by=A.CHOOSE_AT_RUNTIME, requires_payment_selection=True),
    dict(title="طراحی اولیه اتوکد", client_label="طراحی اولیه", kind=StageKind.DESIGN_INITIAL,
         specialty="طراح اتوکد", allows_file_upload=True, estimated_duration_hours=8),
    dict(title="تایید طرح اولیه", client_label="تایید نقشه اولیه", kind=StageKind.DESIGN_APPROVAL,
         approval_by=A.CHOOSE_AT_RUNTIME),
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
         assign_to_project_creator=True, client_visible=False),
]

BASE = dict(kind=StageKind.GENERIC, assign_to_project_creator=False, approval_by=A.NONE,
            requires_payment_selection=False, allows_file_upload=False, client_visible=True,
            estimated_duration_hours=None, client_label="")


def build_workflow_v2(*, make_default=False):
    """idempotent و اصلاح‌کننده: اجرای دوباره، مراحل موجود قالب را طبق STEPS به‌روز می‌کند. خروجی: (template, created)"""
    template, created = WorkflowTemplate.objects.get_or_create(name=TEMPLATE_NAME)
    made = []
    for order, spec in enumerate(STEPS, start=1):
        spec = dict(spec)
        name = spec.pop("specialty", None)
        specialty = Specialty.objects.get_or_create(name=name)[0] if name else None
        step, _ = WorkflowStepTemplate.objects.update_or_create(
            template=template, order=order, defaults={**BASE, "responsible_specialty": specialty, **spec})
        made.append(step)
    made[4].on_reject_go_to = made[3]   # رد تایید طرح ← برگشت به طراحی اولیه
    made[4].save(update_fields=["on_reject_go_to"])
    if make_default:
        WorkflowTemplate.objects.exclude(pk=template.pk).update(is_default=False)
        template.is_default = True
        template.save(update_fields=["is_default"])
    return template, created
