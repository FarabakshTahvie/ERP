import re
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone

from .models import Project, ProjectStage, StageEvent, ProjectService, ProjectMaterial, WorkflowStepTemplate, StageKind

INTAKE_SPECIALTY_NAME = "پذیرش"
ACCOUNTANT_SPECIALTY_NAME = "حسابدار"
NOT_SENT = object()   # برای تاریخ قرارداد در ویرایش: None یعنی «پاک کن»، NOT_SENT یعنی «دست نزن»
FEE_MAX = Decimal(10) ** 12
NOTES_MAX = 2000
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_fee(raw, *, label):
    """
    مبلغ تومان: خالی = صفر؛ ارقام فارسی/عربی و کاما مجاز؛ فقط عدد صحیح نامنفی کمتر از FEE_MAX.
    هر ایرادی ValueError فارسی می‌دهد.
    """
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace(" ", "")
    if not text:
        return Decimal("0")
    if not re.fullmatch(r"\d+", text):
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد صحیح (به تومان) وارد کنید.")
    value = Decimal(int(text))
    if value >= FEE_MAX:
        raise ValueError(f"{label} بیش از حد بزرگ است.")
    return value


def clean_project_notes(raw):
    text = (raw or "").strip()
    if len(text) > NOTES_MAX:
        raise ValueError(f"یادداشت نباید بیش از {NOTES_MAX} کاراکتر باشد.")
    return text


from core.capabilities import can, is_accountant


def user_can_create_projects(user):
    return can(user, "projects.create")


def user_is_accountant(user):
    return is_accountant(user)


def user_can_access_accounting(user):
    """مرکز حسابداری: مدیر، superuser یا حسابدار."""
    return can(user, "accounting.access")


def can_edit_pricing(user, project=None):
    return can(user, "pricing.edit")


def can_search_parties_for_purchase(user):
    """
    جستجوی طرف‌حساب (new_project_party_search) هم برای «پذیرش» و هم برای «انباردار» باز است،
    چون این ویو فقط جستجوی خواندنی است و هیچ نوشتنی در دیتابیس انجام نمی‌دهد؛ محدودیت واقعی
    روی ثبت پروژه/خرید در ویوهای خودشان (project creation / purchase_new) باقی می‌ماند.
    """
    from inventory.services import user_can_manage_inventory
    return user_can_create_projects(user) or user_can_manage_inventory(user)


EDITABLE_PROJECT_STATUSES = (Project.Status.DRAFT, Project.Status.IN_PROGRESS)


def can_edit_project(user, project):
    """مدیر همیشه؛ تکنسین فقط پروژه‌ای که خودش ثبت کرده (و هنوز تخصص «پذیرش» دارد)."""
    from accounts.models import User
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == User.Role.ADMIN:
        return True
    return project.created_by_id == user.id and user_can_create_projects(user)


def project_prices_editable(project):
    """
    قیمت‌ها (خدمات/متریال) فقط تا وقتی قابل ویرایش‌اند که مشتری چیزی را تایید یا پرداخت نکرده باشد:
    پروژه فعال، فاکتور هنوز پیش‌فاکتور، هیچ پرداخت غیررد‌شده‌ای نباشد، و مرحله‌ی تایید پیش‌فاکتور انجام‌نشده باشد.
    """
    from finance.models import Invoice, Payment
    if project.status not in EDITABLE_PROJECT_STATUSES:
        return False
    invoice = getattr(project, "invoice", None)
    if invoice is not None:
        if invoice.document_type != Invoice.DocumentType.PROFORMA:
            return False
        if invoice.payments.exclude(status=Payment.Status.REJECTED).exists():
            return False
    return not project.stages.filter(
        step_template__requires_payment_selection=True, status=ProjectStage.Status.DONE,
    ).exists()


def _clean_lines(lines, model, label):
    """ردیف‌های خام JSON را اعتبارسنجی و به Decimal تبدیل می‌کند؛ هر ایرادی ValueError فارسی می‌دهد."""
    cleaned = []
    for raw in (lines or []):
        try:
            item_id = int(raw["id"])
            qty = Decimal(str(raw["qty"]))
            price = Decimal(str(raw["unit_price"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValueError(f"اطلاعات ردیف‌های {label} نامعتبر است.")
        if not qty.is_finite() or not price.is_finite() or qty <= 0 or price < 0:
            raise ValueError(f"در ردیف‌های {label}، مقدار باید بزرگ‌تر از صفر و قیمت نامنفی باشد.")
        try:
            pk = int(raw.get("pk")) if raw.get("pk") not in (None, "") else None
        except (TypeError, ValueError):
            pk = None
        cleaned.append({"id": item_id, "qty": qty, "unit_price": price, "pk": pk})
    ids = {c["id"] for c in cleaned}
    if ids and model.objects.filter(pk__in=ids).count() != len(ids):
        raise ValueError(f"یکی از موارد {label} در سیستم پیدا نشد.")
    return cleaned


def _to_coordinate(value, limit):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value)).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        raise ValueError("مختصات نامعتبر است.")
    if abs(number) > limit:
        raise ValueError("مختصات نامعتبر است.")
    return number


def _location_is_shared(location, project):
    return location.projects.exclude(pk=project.pk).exists() or location.parties.exists()


def _sync_project_lines(model, fk_name, project, lines):
    """
    ردیف‌های دارای pk همان رکورد را به‌روز می‌کنند (فیلدهایی مثل «توضیحات» حفظ می‌شود)،
    بقیه ساخته می‌شوند و ردیف‌های حذف‌شده پاک می‌شوند. خروجی: آیا چیزی تغییر کرد؟
    """
    existing = {obj.pk: obj for obj in model.objects.filter(project=project)}
    keep, changed = set(), False
    for line in lines:
        obj = existing.get(line["pk"]) if line["pk"] not in keep else None
        if obj is None:
            obj = model(project=project)
            changed = True
        elif (getattr(obj, f"{fk_name}_id"), obj.qty, obj.unit_price) != (line["id"], line["qty"], line["unit_price"]):
            changed = True
        setattr(obj, f"{fk_name}_id", line["id"])
        obj.qty = line["qty"]
        obj.unit_price = line["unit_price"]
        obj.save()
        keep.add(obj.pk)
    deleted, _ = model.objects.filter(project=project).exclude(pk__in=keep).delete()
    return changed or deleted > 0


@transaction.atomic
def update_project_from_technician_edit(*, project, actor, location_lat=None, location_lng=None,
                                         location_address="", service_lines=None, material_lines=None,
                                         installation_fee_raw=None, shipping_fee_raw=None, extra_fee_raw=None,
                                         contract_date=NOT_SENT, notes=None):
    """
    service_lines/material_lines برابر None یعنی «ارسال نشده، دست نزن».
    خروجی: (project, پیش‌فاکتور بازتولید شد؟)
    """
    from catalog.models import Service, Item
    from core.models import Location
    from .models import ProjectService, ProjectMaterial

    if not can_edit_project(actor, project):
        raise ValueError("شما اجازه‌ی ویرایش این پروژه را ندارید.")
    if project.status not in EDITABLE_PROJECT_STATUSES:
        raise ValueError("پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")

    prices_open = project_prices_editable(project)
    fees_sent = any(v is not None for v in (installation_fee_raw, shipping_fee_raw, extra_fee_raw))
    costs_touched = fees_sent or contract_date is not NOT_SENT
    pricing_touched = service_lines is not None or material_lines is not None or costs_touched
    if pricing_touched and not can_edit_pricing(actor, project):
        raise ValueError("تغییر خدمات، قیمت‌ها و اطلاعات قرارداد فقط با حسابدار یا مدیر است.")
    if (service_lines is not None or material_lines is not None or costs_touched) and not prices_open:
        raise ValueError(
            "قیمت‌ها و اطلاعات قرارداد قفل شده‌اند (پیش‌فاکتور تایید شده یا پرداختی ثبت شده). "
            "فقط آدرس، موقعیت و یادداشت قابل ویرایش است."
        )

    service_lines = None if service_lines is None else _clean_lines(service_lines, Service, "خدمات")
    material_lines = None if material_lines is None else _clean_lines(material_lines, Item, "متریال")

    new_fees = {}
    for field, raw, label in (
        ("installation_fee", installation_fee_raw, "هزینه نصب"),
        ("shipping_fee", shipping_fee_raw, "هزینه ارسال"),
        ("extra_fee", extra_fee_raw, "هزینه مازاد"),
    ):
        if raw is not None:
            new_fees[field] = parse_fee(raw, label=label)
    notes = None if notes is None else clean_project_notes(notes)

    # --- موقعیت ---
    lat, lng = _to_coordinate(location_lat, 90), _to_coordinate(location_lng, 180)
    if lat is None or lng is None:
        lat = lng = None
    address = (location_address or "").strip()
    old_location = project.location
    if lat is None and not address:
        new_location = None
    elif old_location and not _location_is_shared(old_location, project):
        old_location.latitude, old_location.longitude, old_location.address_text = lat, lng, address
        old_location.save()
        new_location = old_location
    else:
        new_location = Location.objects.create(latitude=lat, longitude=lng, address_text=address)
    project.location = new_location
    
    fees_changed = False
    for field, value in new_fees.items():
        if getattr(project, field) != value:
            setattr(project, field, value)
            fees_changed = True
    date_changed = contract_date is not NOT_SENT and project.contract_date != contract_date
    if date_changed:
        project.contract_date = contract_date
    if notes is not None:
        project.notes = notes
    update_fields = ["location", "updated_at", *new_fees]
    if date_changed:
        update_fields.append("contract_date")
    if notes is not None:
        update_fields.append("notes")
    project.save(update_fields=update_fields)   # برای ثبت در تاریخچه‌ی پروژه

    # --- ردیف‌ها ---
    lines_changed = False
    if service_lines is not None:
        lines_changed |= _sync_project_lines(ProjectService, "service", project, service_lines)
    if material_lines is not None:
        lines_changed |= _sync_project_lines(ProjectMaterial, "item", project, material_lines)

    # --- فاکتور (فقط تا وقتی قیمت‌ها باز است؛ بعدش آدرس فاکتور همان اسنپ‌شات صدور می‌ماند) ---
    invoice = getattr(project, "invoice", None)
    rebuilt = False
    if prices_open and invoice is not None:
        invoice.address_snapshot = new_location.address_text if new_location else ""
        invoice_fields = ["address_snapshot"]
        if date_changed:
            invoice.contract_date = project.contract_date
            invoice_fields.append("contract_date")
        invoice.save(update_fields=invoice_fields)
        if lines_changed or fees_changed:
            from finance.services import refresh_invoice_lines
            refresh_invoice_lines(invoice)
            rebuilt = True
    return project, rebuilt


@transaction.atomic
def create_project_stages_from_template(project):
    if not project.workflow_template:
        raise ValueError("پروژه هیچ قالب گردش‌کاری ندارد.")
    if project.stages.exists():
        raise ValueError("این پروژه قبلاً مراحل خود را دارد.")

    steps = project.workflow_template.steps.order_by("order")
    stages = [
        ProjectStage(
            project=project,
            step_template=step,
            order=step.order,
            title=step.title,
            client_label=step.client_label,
            kind=step.kind,
            client_visible=step.client_visible,
            status=ProjectStage.Status.PENDING,
        )
        for step in steps
    ]
    ProjectStage.objects.bulk_create(stages)

    first_stage = project.stages.select_related("step_template", "project").order_by("order").first()
    if first_stage:
        first_stage.status = ProjectStage.Status.IN_PROGRESS
        first_stage.started_at = timezone.now()
        _assign_stage_responsible(first_stage)
        first_stage.save()

    if project.status == Project.Status.DRAFT:
        project.status = Project.Status.IN_PROGRESS
        project.save(update_fields=["status"])

    return list(project.stages.order_by("order"))


@transaction.atomic
def advance_stage(stage, actor, new_status, comment):
    if not comment or not comment.strip():
        raise ValueError("ثبت توضیح برای این مرحله اجباری است.")

    from accounts.models import User
    is_accountant_on_final_review = stage.kind == StageKind.FINAL_REVIEW and user_is_accountant(actor)
    if (getattr(actor, "role", None) == User.Role.EMPLOYEE and stage.assigned_to_id
            and stage.assigned_to_id != actor.id and not is_accountant_on_final_review):
        raise ValueError("فقط مسئول این مرحله می‌تواند وضعیتش را تغییر دهد.")

    if (stage.kind == StageKind.PROFORMA and new_status == ProjectStage.Status.DONE
            and not hasattr(stage.project, "invoice")):
        raise ValueError("پیش‌فاکتور هنوز صادر نشده است.")

    old_status = stage.status
    if new_status == ProjectStage.Status.DONE:
        stage.status = new_status
        stage.completed_at = timezone.now()
        stage.completed_by = actor
        stage.save()
    elif new_status == ProjectStage.Status.REJECTED:
        stage.rejection_count += 1
        if stage.step_template.on_reject_go_to:
            stage.status = ProjectStage.Status.REJECTED
            stage.save(update_fields=["status", "rejection_count"])
            target_stage = stage.project.stages.filter(step_template=stage.step_template.on_reject_go_to).first()
            if target_stage:
                target_stage.status = ProjectStage.Status.IN_PROGRESS
                target_stage.save(update_fields=["status"])
        else:
            # هیچ مسیر اصلاح خودکاری تعریف نشده → معلق تا بررسی مدیر
            stage.status = ProjectStage.Status.SUSPENDED
            stage.save(update_fields=["status", "rejection_count"])
    else:
        stage.status = new_status
        stage.save()

    StageEvent.objects.create(
        stage=stage,
        actor=actor,
        from_status=old_status,
        to_status=stage.status,
        comment=comment,
    )

    if new_status == ProjectStage.Status.DONE:
        if stage.return_to_id:
            _resume_parked(stage)
        else:
            _activate_next_stage(stage)

    return stage


def _assign_stage_responsible(stage):
    """مسئول مرحله را هنگام شروع تعیین می‌کند (قانون ۵). خروجی: کاربران برای اطلاع‌رسانی (فعلاً TODO)."""
    from accounts.models import User
    template = stage.step_template
    if template.default_assignee_id:
        stage.assigned_to = template.default_assignee
        return [template.default_assignee]
    if template.assign_to_project_creator and stage.project.created_by_id:
        stage.assigned_to_id = stage.project.created_by_id
        return [stage.project.created_by]
    if template.responsible_specialty_id:
        candidates = list(User.objects.filter(
            role=User.Role.EMPLOYEE, specialties=template.responsible_specialty, is_active=True,
        ))
        stage.save()
        stage.candidate_users.set(candidates)
        return candidates
    if template.responsible_role:
        return list(User.objects.filter(role=template.responsible_role, is_active=True))
    return []


EXTERNAL_APPROVAL_TYPES = (
    WorkflowStepTemplate.ApprovalBy.PARTNER,
    WorkflowStepTemplate.ApprovalBy.OWNER,
    WorkflowStepTemplate.ApprovalBy.CHOOSE_AT_RUNTIME,
)


def _resume_parked(stage):
    """مرحله‌ی بازشده با انتقال تمام شد؛ پروژه به مرحله‌ی متوقف برمی‌گردد."""
    parked = ProjectStage.objects.select_related("step_template", "project").get(pk=stage.return_to_id)
    ProjectStage.objects.filter(pk=stage.pk).update(return_to=None)
    if parked.status != ProjectStage.Status.PENDING:
        return
    StageEvent.objects.create(stage=parked, actor=None, from_status=parked.status,
                              to_status=ProjectStage.Status.IN_PROGRESS,
                              comment=f"بعد از تکمیل «{stage.title}» به این مرحله برگشت.")
    if parked.step_template.approval_by in EXTERNAL_APPROVAL_TYPES:
        send_stage_for_approval(parked)   # درخواست قبلی لغو شده بود؛ دوباره برای مشتری می‌رود
        return
    parked.status = ProjectStage.Status.IN_PROGRESS
    if not parked.assigned_to_id and not parked.candidate_users.exists():
        _assign_stage_responsible(parked)
    parked.save()


def _activate_next_stage(stage):
    next_stage = (
        stage.project.stages.filter(
            order__gt=stage.order,
            status__in=(ProjectStage.Status.PENDING, ProjectStage.Status.REJECTED),
        ).order_by("order").first()
    )
    if not next_stage:
        project = stage.project
        if project.status != Project.Status.CANCELLED:
            project.status = Project.Status.COMPLETED
            project.actual_end_date = timezone.localdate()
            project.save(update_fields=["status", "actual_end_date"])
        return

    template = next_stage.step_template
    if template.approval_by in EXTERNAL_APPROVAL_TYPES:
        next_stage.save()
        send_stage_for_approval(next_stage)
        return

    # approval_by == NONE یا ADMIN: هر دو دقیقاً یکسان رفتار می‌کنن (رفتار قبلی، بدون تغییر).
    # عمداً ADMIN اینجا کنار NONE گذاشته شده، نه کنار بقیه‌ی approval_by‌ها، چون این فیلد
    # طبق تصمیم قبلی پروژه هنوز به هیچ سرویسی وصل نیست و نباید مرحله‌ی «نصب» (که هم‌زمان
    # تخصص کانال‌کش هم داره) رو از چرخه‌ی ارجاع تکنسین خارج کنه.
    next_stage.status = ProjectStage.Status.IN_PROGRESS
    next_stage.started_at = timezone.now()
    notify_users = _assign_stage_responsible(next_stage)   # noqa: F841
    next_stage.save()
    # TODO(نوتیفیکیشن ارجاع کار): طبق تصمیم قبلی کاربر، همچنان کامنت بمونه.


@transaction.atomic
def claim_stage(stage, user):
    """کاربری که در candidate_users هست (یا ادمین) این کار را رسماً برمی‌دارد."""
    from accounts.models import User
    from .models import ProjectStage
    if stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("این مرحله در حال انجام نیست.")
    if stage.assigned_to_id:
        raise ValueError("این مرحله قبلاً به شخص دیگری اختصاص یافته است.")
    if user.role != User.Role.ADMIN and not stage.candidate_users.filter(pk=user.pk).exists():
        raise ValueError("شما جزو افراد واجد شرایط این مرحله نیستید.")
    stage.assigned_to = user
    stage.candidate_users.clear()
    stage.save(update_fields=["assigned_to"])
    StageEvent.objects.create(stage=stage, actor=user, from_status=stage.status, to_status=stage.status, comment="کار را برداشت.")
    return stage


def resolve_billing_party(project):
    """
    چه کسی صورت‌حساب می‌شود: اولویت با شریک تجاری واقعی (نه شرکت خودمان)،
    وگرنه صاحب ملک/کارفرما، وگرنه (حالت خطا) خود شریک تجاری.
    """
    if project.partner_id and not project.partner.is_internal:
        return project.partner
    return project.owner or project.partner


def stage_approval_action(stage, invoice=None):
    """
    لینک و برچسب دکمه‌ی مشتری برای مرحله‌ی «در انتظار تایید». خروجی: (url, label) یا (None, None).
    تنها منبع برای صفحه‌ی خانه و صفحه‌ی مراحل مشتری.
    """
    from django.urls import reverse
    from .models import StageApproval
    if stage.status != ProjectStage.Status.WAITING_APPROVAL:
        return None, None
    approval = stage.approvals.filter(decision=StageApproval.Decision.PENDING).first()
    if not approval:
        return None, None
    if stage.step_template.requires_payment_selection and invoice:
        return reverse("finance:portal_invoice_detail", args=[invoice.uuid]), "مشاهده و تایید فاکتور"
    return reverse("projects:portal_stage_approval", args=[approval.id]), "مشاهده و تایید این مرحله"


def default_approval_party(project):
    return resolve_billing_party(project)


@transaction.atomic
def assign_stage(stage, target_user, actor, comment):
    """
    ارجاع مستقیم مدیر. فقط مرحله‌ی «در حال انجام» از پروژه‌ی در حال اجرا.
    هدف باید تکنسین فعال باشد؛ تخصص اجباری نیست (خارج از تخصص در سابقه ثبت می‌شود)،
    ولی صدور پیش‌فاکتور و بازبینی نهایی فقط به حسابدار داده می‌شود.
    """
    from accounts.models import User
    from core.capabilities import can
    if not can(actor, "stages.assign"):
        raise ValueError("فقط مدیر می‌تواند مرحله را آزادانه به هرکسی ارجاع دهد.")
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("ثبت دلیل ارجاع دستی اجباری است.")
    if target_user is None:
        raise ValueError("مسئول جدید را انتخاب کنید.")
    stage = (ProjectStage.objects.select_for_update()
             .select_related("project", "step_template", "assigned_to").get(pk=stage.pk))
    if stage.project.status != Project.Status.IN_PROGRESS:
        raise ValueError("پروژه در حال اجرا نیست.")
    if stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("فقط مرحله‌ی «در حال انجام» قابل ارجاع است.")
    if not target_user.is_active or target_user.role != User.Role.EMPLOYEE:
        raise ValueError("مسئول باید یک تکنسین فعال باشد.")
    if stage.assigned_to_id == target_user.id:
        raise ValueError("این کار همین الان به همین شخص سپرده شده است.")
    if stage.kind == StageKind.PROFORMA and not can(target_user, "pricing.edit"):
        raise ValueError("صدور پیش‌فاکتور فقط به حسابدار ارجاع داده می‌شود.")
    if stage.kind == StageKind.FINAL_REVIEW and not can(target_user, "final_review.view"):
        raise ValueError("بازبینی نهایی فقط به حسابدار ارجاع داده می‌شود.")

    specialty = stage.step_template.responsible_specialty
    off_specialty = bool(specialty and not target_user.specialties.filter(pk=specialty.pk).exists())
    name = target_user.get_full_name() or target_user.username
    stage.assigned_to = target_user
    stage.candidate_users.clear()
    stage.save(update_fields=["assigned_to", "updated_at"])
    StageEvent.objects.create(
        stage=stage, actor=actor, from_status=stage.status, to_status=stage.status,
        comment=f"ارجاع مدیر به {name}: {comment}" + (" [خارج از تخصص مرحله]" if off_specialty else ""))
    # TODO(اعلان ارجاع به تکنسین): فاز ۴-د
    return stage


@transaction.atomic
def resume_suspended_stage(stage, actor, comment):
    """بازگشت مرحله‌ی معلق به چرخه. مرحله‌ی تاییدِ مشتری دوباره برای مشتری فرستاده می‌شود."""
    from core.capabilities import can
    if not can(actor, "stages.assign"):
        raise ValueError("فقط مدیر می‌تواند مرحله‌ی معلق را به چرخه برگرداند.")
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("ثبت دلیل بازگشت به چرخه اجباری است.")
    stage = (ProjectStage.objects.select_for_update()
             .select_related("project", "step_template").get(pk=stage.pk))
    if stage.status != ProjectStage.Status.SUSPENDED:
        raise ValueError("این مرحله معلق نیست.")
    if stage.project.status != Project.Status.IN_PROGRESS:
        raise ValueError("پروژه در حال اجرا نیست.")
    old = stage.status
    if stage.step_template.approval_by in EXTERNAL_APPROVAL_TYPES:
        send_stage_for_approval(stage, sent_by=actor)   # وضعیت را WAITING_APPROVAL می‌کند
        text = f"بازگشت به چرخه توسط مدیر؛ دوباره برای تایید ارسال شد: {comment}"
    else:
        stage.status = ProjectStage.Status.IN_PROGRESS
        stage.save(update_fields=["status", "updated_at"])
        if not stage.assigned_to_id and not stage.candidate_users.exists():
            _assign_stage_responsible(stage)
            stage.save()
        text = f"بازگشت به چرخه توسط مدیر: {comment}"
    StageEvent.objects.create(stage=stage, actor=actor, from_status=old, to_status=stage.status, comment=text)
    return stage


@transaction.atomic
def cancel_project_from_stage(stage, actor, comment, *, cancel_invoice=False):
    """
    لغو پروژه (فقط مدیر). درخواست‌های تاییدِ باز لغو می‌شوند.
    cancel_invoice=True: فاکتور هم لغو می‌شود؛ اگر فاکتور پرداخت تاییدشده داشته باشد
    کل عملیات (از جمله لغو پروژه) برمی‌گردد.
    """
    from core.capabilities import can
    from finance.models import Invoice
    from .models import StageApproval
    if not can(actor, "projects.cancel"):
        raise ValueError("فقط مدیر می‌تواند پروژه را لغو کند.")
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("ثبت دلیل لغو پروژه اجباری است.")
    project = Project.objects.select_for_update().get(pk=stage.project_id)
    if project.status == Project.Status.CANCELLED:
        raise ValueError("این پروژه قبلاً لغو شده است.")
    if project.status == Project.Status.COMPLETED:
        raise ValueError("پروژه‌ی تکمیل‌شده قابل لغو نیست.")

    invoice_note = ""
    invoice = getattr(project, "invoice", None)
    if cancel_invoice and invoice is not None and invoice.status != Invoice.Status.CANCELLED:
        from finance.services import cancel_invoice as cancel_invoice_service
        cancel_invoice_service(invoice=invoice, reason=f"لغو پروژه: {comment}", actor=actor)
        invoice_note = " (فاکتور هم لغو شد)"

    project.status = Project.Status.CANCELLED
    project.save(update_fields=["status", "updated_at"])
    StageApproval.objects.filter(stage__project=project, decision=StageApproval.Decision.PENDING).update(
        decision=StageApproval.Decision.CANCELLED, decided_at=timezone.now())
    stage = ProjectStage.objects.get(pk=stage.pk)
    old = stage.status
    stage.status = ProjectStage.Status.REJECTED
    stage.save(update_fields=["status", "updated_at"])
    StageEvent.objects.create(stage=stage, actor=actor, from_status=old, to_status=stage.status,
                              comment=f"پروژه لغو شد{invoice_note}: {comment}")



@transaction.atomic
def send_stage_for_approval(stage, party=None, sent_by=None):
    if not party:
        party = default_approval_party(stage.project)
    from .models import StageApproval
    approval = StageApproval.objects.create(stage=stage, sent_to_party=party, sent_by=sent_by)
    stage.status = ProjectStage.Status.WAITING_APPROVAL
    stage.save(update_fields=["status"])

    user = party.users.first()
    if user:
        from notifications.services import create_notification
        from notifications.models import NotificationType
        create_notification(
            notification_type=NotificationType.STAGE_APPROVAL_REQUEST, user=user,
            title="نیاز به تایید شما",
            body=f"مرحله «{stage.client_label or stage.title}» از پروژه «{stage.project.name}» نیاز به تایید شما دارد.",
            real_target_url=f"/portal/approvals/{approval.id}/",
        )
    return approval


@transaction.atomic
def decide_stage_approval(approval, actor, decision, comment=""):
    from .models import StageApproval
    if decision == StageApproval.Decision.REJECTED and (not comment or not comment.strip()):
        raise ValueError("برای رد یک مرحله، ذکر دلیل اجباری است.")

    approval.decision = decision
    approval.decided_at = timezone.now()
    approval.comment = comment
    approval.save()

    stage = approval.stage
    if decision == StageApproval.Decision.APPROVED:
        advance_stage(stage, actor=actor, new_status=ProjectStage.Status.DONE, comment=comment or "تایید شد توسط کارفرما/شریک")
    elif decision == StageApproval.Decision.REJECTED:
        advance_stage(stage, actor=actor, new_status=ProjectStage.Status.REJECTED, comment=comment)

    return approval


def get_transfer_candidates(stage):
    """تکنسین‌های فعال و هم‌تخصص با نیازمندی همین مرحله، به‌جز خودِ مسئول فعلی."""
    from accounts.models import User
    qs = User.objects.filter(role=User.Role.EMPLOYEE, is_active=True)
    if stage.assigned_to_id:
        qs = qs.exclude(pk=stage.assigned_to_id)
    specialty = stage.step_template.responsible_specialty
    if specialty:
        qs = qs.filter(specialties=specialty)
    return qs.distinct().order_by("first_name", "last_name")


@transaction.atomic
def transfer_stage(stage, from_user, to_user, comment=""):
    """
    انتقال مستقیم توسط خودِ مسئول فعلی — بدون نیاز به تایید طرف مقابل.
    فقط کسی که همین الان assigned_to هست می‌تواند انتقال بدهد.
    """
    from accounts.models import User
    from .models import ProjectStage
    if stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("این مرحله در حال انجام نیست.")
    if stage.assigned_to_id != from_user.id:
        raise ValueError("فقط مسئول فعلی این مرحله می‌تواند آن را انتقال دهد.")
    if to_user.role != User.Role.EMPLOYEE:
        raise ValueError("مرحله فقط قابل انتقال به یک تکنسین است.")
    if to_user.id == from_user.id:
        raise ValueError("نمی‌توانید کار را به خودتان انتقال دهید.")

    specialty = stage.step_template.responsible_specialty
    if specialty and not to_user.specialties.filter(pk=specialty.pk).exists():
        raise ValueError("تکنسین مقصد دارای تخصص لازم برای این مرحله نیست.")

    old_name = from_user.get_full_name() or from_user.username
    new_name = to_user.get_full_name() or to_user.username

    stage.assigned_to = to_user
    stage.candidate_users.clear()
    stage.save(update_fields=["assigned_to"])

    StageEvent.objects.create(
        stage=stage, actor=from_user, from_status=stage.status, to_status=stage.status,
        comment=comment.strip() if comment and comment.strip() else f"کار توسط {old_name} به {new_name} منتقل شد.",
    )
    return stage


MAX_INTAKE_FILES = 20


def attach_project_files(project, stage, files, *, uploader):
    files = [f for f in (files or []) if f]
    if len(files) > MAX_INTAKE_FILES:
        raise ValueError(f"حداکثر {MAX_INTAKE_FILES} فایل را می‌توان یک‌جا ارسال کرد.")
    from .models import ProjectFile
    from utils.utils import guess_file_kind
    for f in files:
        ProjectFile.objects.create(
            stage=stage, file=f, kind=guess_file_kind(f.name),
            original_name=(f.name or "")[:255], uploaded_by=uploader, is_attachment=True,
        )


def _require_v2_template(template):
    first = template.steps.order_by("order").first()
    if not first or first.kind != StageKind.VISIT:
        raise ValueError("گردش‌کار پیش‌فرض نسخه‌ی جدید نیست؛ ابتدا دستور setup_workflow_v2 --make-default اجرا شود.")


@transaction.atomic
def update_visit_date(*, project, actor, visit_date):
    if not can_edit_project(actor, project):
        raise ValueError("شما اجازه‌ی ویرایش این پروژه را ندارید.")
    if visit_date is None:
        raise ValueError("تاریخ بازدید را مشخص کنید.")
    visit_stage = project.stages.filter(kind=StageKind.VISIT).first()
    if visit_stage and visit_stage.status == ProjectStage.Status.DONE:
        raise ValueError("بازدید انجام شده و تاریخ آن قابل تغییر نیست.")
    project.visit_date = visit_date
    project.save(update_fields=["visit_date", "updated_at"])
    # TODO(پیامک تغییر زمان بازدید به طرف‌حساب): قالب پیامک هنوز آماده نیست.


# نام قدیمی برای سازگاری موقت
update_visit_at = update_visit_date


@transaction.atomic
def create_project_from_technician_intake(*, created_by, party_id=None, party_data=None,
                                           owner_party_id=None, owner_party_data=None,
                                           location_lat=None, location_lng=None, location_address="",
                                           service_lines=None, material_lines=None,
                                           installation_fee_raw="", shipping_fee_raw="", extra_fee_raw="",
                                           contract_date=None, notes="", send_sms=False, visit_date=None, visit_at=None,
                                           uploaded_files=None, issue_proforma=True):
    from core.models import Party, Location
    from catalog.models import Service, Item
    if visit_date is None and visit_at is not None:
        visit_date = visit_at.date() if hasattr(visit_at, "date") else visit_at
    service_lines = _clean_lines(service_lines, Service, "خدمات")
    material_lines = _clean_lines(material_lines, Item, "متریال")
    installation_fee = parse_fee(installation_fee_raw, label="هزینه نصب")
    shipping_fee = parse_fee(shipping_fee_raw, label="هزینه ارسال")
    extra_fee = parse_fee(extra_fee_raw, label="هزینه مازاد")
    notes = clean_project_notes(notes)
    if not issue_proforma and visit_date is None:
        raise ValueError("تاریخ بازدید را مشخص کنید.")

    if party_id:
        party = Party.objects.get(pk=party_id)
    else:
        if not party_data or not party_data.get("phone_number"):
            raise ValueError("اطلاعات طرف‌حساب ناقص است.")
        if Party.objects.filter(phone_number=party_data["phone_number"]).exists():
            raise ValueError("طرف‌حسابی با این شماره از قبل وجود دارد؛ لطفاً همان را انتخاب کنید.")
        party = Party.objects.create(**party_data)

    if owner_party_id:
        owner = Party.objects.get(pk=owner_party_id)
    elif owner_party_data and owner_party_data.get("phone_number"):
        if Party.objects.filter(phone_number=owner_party_data["phone_number"]).exists():
            raise ValueError("طرف‌حسابی با این شماره (صاحب ملک) از قبل وجود دارد؛ لطفاً همان را انتخاب کنید.")
        owner = Party.objects.create(**owner_party_data)
    else:
        owner = party

    location = None
    has_coords = bool(location_lat and location_lng)
    address = (location_address or "").strip()
    if has_coords or address:
        location = Location.objects.create(
            latitude=location_lat if has_coords else None,
            longitude=location_lng if has_coords else None,
            address_text=address,
        )

    from .models import WorkflowTemplate
    template = WorkflowTemplate.objects.filter(is_default=True).first()
    if not template:
        raise ValueError("هیچ قالب گردش‌کار پیش‌فرضی تعریف نشده است.")
    if not issue_proforma:
        _require_v2_template(template)

    internal_party = Party.objects.filter(is_internal=True).first()
    if not internal_party:
        raise ValueError("طرف‌حساب داخلی شرکت تعریف نشده است.")
    partner = party if party.is_partner else internal_party

    proj_name = (party_data.get("brand_name") or party_data["name"]) if party_data else (party.brand_name or party.name)

    project = Project.objects.create(
        name=proj_name, partner=partner, owner=owner, location=location,
        workflow_template=template, created_by=created_by, status=Project.Status.IN_PROGRESS,
        installation_fee=installation_fee, shipping_fee=shipping_fee, extra_fee=extra_fee,
        contract_date=contract_date, visit_date=visit_date, notes=notes,
    )

    for line in (service_lines or []):
        ProjectService.objects.create(
            project=project, service_id=line["id"], qty=line["qty"], unit_price=line["unit_price"],
        )
    for line in (material_lines or []):
        ProjectMaterial.objects.create(
            project=project, item_id=line["id"], qty=line["qty"], unit_price=line["unit_price"],
        )

    stages = create_project_stages_from_template(project)

    if uploaded_files:
        attach_project_files(project, stages[0], uploaded_files, uploader=created_by)
    if not issue_proforma:
        # TODO(پیامک زمان بازدید به طرف‌حساب): قالب پیامک هنوز آماده نیست؛ فقط کامنت.
        return project, None, False

    from finance.services import generate_invoice_for_project, ensure_billed_party_account, notify_invoice_issued
    invoice = generate_invoice_for_project(project)
    user, raw_password = ensure_billed_party_account(invoice)

    advance_stage(stages[0], actor=created_by, new_status=ProjectStage.Status.DONE, comment="پیش‌فاکتور صادر و ثبت شد.")

    account_conflict = user is None
    if send_sms and user:
        notify_invoice_issued(invoice, user, raw_password)

    return project, invoice, account_conflict
