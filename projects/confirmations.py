from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Project, ProjectFile, ProjectStage, StageConfirmation, StageKind
from .services import resolve_billing_party

D = StageConfirmation.Decision
CONFIRM_KINDS = (StageKind.SHIPPING, StageKind.INSTALL)
ALLOWED = {StageKind.SHIPPING: (D.RECEIVED, D.NOT_RECEIVED), StageKind.INSTALL: (D.CONFIRMED,)}


def confirmation_path(stage_id):
    """مسیر صفحه‌ی مشتری (در بریف ۲ با نام URL هم‌خوان می‌شود؛ تست نگهبانش آنجاست)."""
    return f"/portal/stage-confirmations/{stage_id}/"


def is_recipient_party(user, project):
    """طرف‌حسابِ صورت‌حساب پروژه؛ پیامک به حساب او می‌رود و فقط او می‌تواند پاسخ بدهد."""
    party = getattr(user, "party", None)
    billing = resolve_billing_party(project)
    return bool(party and billing and party.id == billing.id)


def open_confirmation(stage):
    """بعد از تکمیل مرحله‌ی ارسال یا نصب (داخل تراکنش complete_stage). برای هر مرحله فقط یک بار."""
    if stage.kind not in CONFIRM_KINDS:
        return None
    from notifications.models import NotificationType
    from notifications.services import notify_users
    project = stage.project
    party = resolve_billing_party(project)
    user = party.users.filter(is_active=True).first() if party else None
    conf, created = StageConfirmation.objects.get_or_create(stage=stage, defaults={"recipient": user})
    if not created or user is None:
        return conf
    if stage.kind == StageKind.SHIPPING:
        kind, title = NotificationType.SHIPMENT_SENT, "اقلام پروژه ارسال شد"
        body = f"اقلام پروژه «{project.name}» به محل ارسال شد. لطفا دریافت آن را تایید کنید."
    else:
        kind, title = NotificationType.INSTALL_DONE, "نصب پروژه انجام شد"
        body = f"نصب پروژه «{project.name}» انجام شد. تصاویر را ببینید و تایید کنید."
    notify_users([user], notification_type=kind, title=title, body=body,
                 real_target_url=confirmation_path(stage.id), extra_data={"project_name": project.name})
    return conf


def record_view(conf):
    now = timezone.now()
    rows = StageConfirmation.objects.filter(pk=conf.pk)
    rows.filter(first_viewed_at__isnull=True).update(first_viewed_at=now)
    rows.update(view_count=F("view_count") + 1, last_viewed_at=now)


def _notify_not_received(project, stage):
    """مشتری «دریافت نشد» زد؛ مدیر باید پیگیری کند (بعد از commit؛ تکرار همان پاسخ دوباره خبر نمی‌دهد)."""
    from django.urls import reverse
    from notifications.models import NotificationType
    from notifications.services import notify_staff
    notify_staff("dashboard.manager", notification_type=NotificationType.SHIPMENT_NOT_RECEIVED,
                 title="مشتری اقلام را دریافت نکرد",
                 body=f"مشتریِ پروژه «{project.name}» برای مرحله «{stage.title}» «دریافت نشد» را زد؛ با او تماس بگیرید.",
                 real_target_url=reverse("projects:staff_project_overview", args=[project.pk]))


@transaction.atomic
def set_decision(*, stage_id, decision, actor):
    """صریح و idempotent. تکرار همان پاسخ زمان پاسخ را عوض نمی‌کند."""
    conf = (StageConfirmation.objects.select_for_update(of=("self",))
            .select_related("stage__project").filter(stage_id=stage_id).first())
    if conf is None:
        raise ValueError("این صفحه پیدا نشد.")
    stage, project = conf.stage, conf.stage.project
    if not is_recipient_party(actor, project):
        raise ValueError("این پاسخ را فقط خود مشتری ثبت می‌کند.")
    if project.status == Project.Status.CANCELLED:
        raise ValueError("این پروژه لغو شده است.")
    if stage.status != ProjectStage.Status.DONE:
        raise ValueError("این مرحله هنوز تمام نشده است.")
    if decision not in ALLOWED.get(stage.kind, ()):
        raise ValueError("پاسخ نامعتبر است.")
    if conf.decision == decision:
        return conf
    conf.decision, conf.decided_at, conf.decided_by = decision, timezone.now(), actor
    conf.save(update_fields=["decision", "decided_at", "decided_by"])
    if decision == D.NOT_RECEIVED:
        _notify_not_received(project, stage)
    return conf


def shipped_services(project):
    """فقط نام و مقدار خدمات پیش‌فاکتور؛ نه کالا، نه قیمت."""
    return [{"name": ps.service.name, "qty": ps.qty,
             "unit": ps.service.get_unit_display() if ps.service.unit else ""}
            for ps in project.services.select_related("service").order_by("pk")]


def install_images(stage):
    return [f for f in stage.files.filter(kind=ProjectFile.Kind.IMAGE).order_by("created_at", "pk")
            if f.is_displayable_image]
