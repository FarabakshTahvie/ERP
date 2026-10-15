from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch

from core.capabilities import can
from .models import Project, ProjectCost, ProjectFile, ProjectStage, ServiceTick, StageEvent, StageKind
from .services import parse_fee
from .stage_ops import _is_manager

REASON_MAX = 1000
_ACTIVE = (ProjectStage.Status.IN_PROGRESS, ProjectStage.Status.DONE)


def _reason(raw, *, required, label="دلیل"):
    text = (raw or "").strip()
    if required and not text:
        raise ValueError(f"نوشتن «{label}» اجباری است.")
    if len(text) > REASON_MAX:
        raise ValueError(f"«{label}» بیش از حد طولانی است.")
    return text


def is_creator_or_manager(user, project):
    return user.is_authenticated and (_is_manager(user) or project.created_by_id == user.id)


def can_view_final_review(user, project):
    return can(user, "final_review.view")


def review_open(project):
    st = project.stages.filter(kind=StageKind.FINAL_REVIEW).first()
    return st is None or st.status != ProjectStage.Status.DONE


def can_edit_ops(user, stage):
    """نصاب/راننده/... فقط تا وقتی مرحله‌ی خودشان در حال انجام است؛ ثبت‌کننده‌ی پروژه و مدیر تا قبل از تایید بازبینی نهایی."""
    project = stage.project
    if not user.is_authenticated or project.status == Project.Status.CANCELLED:
        return False
    if is_creator_or_manager(user, project):
        return stage.status in _ACTIVE and review_open(project)
    return stage.assigned_to_id == user.id and stage.status == ProjectStage.Status.IN_PROGRESS


def _log(stage, actor, text):
    StageEvent.objects.create(stage=stage, actor=actor, from_status=stage.status, to_status=stage.status, comment=text)


# ---------------- هزینه‌ها ----------------
def can_manage_costs(user, project):
    return can(user, "costs.manage")


@transaction.atomic
def add_project_cost(*, project, kind, title, amount_raw, actor):
    if not can_manage_costs(actor, project):
        raise ValueError("فقط حسابدار می‌تواند هزینه ثبت کند.")
    if kind not in ProjectCost.Kind.values:
        raise ValueError("نوع هزینه معتبر نیست.")
    amount = parse_fee(amount_raw, label="مبلغ")
    if amount <= 0:
        raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد.")
    return ProjectCost.objects.create(project=project, kind=kind, title=_reason(title, required=True, label="شرح"),
                                      amount=amount, created_by=actor)


@transaction.atomic
def delete_project_cost(*, cost, actor):
    if not can_manage_costs(actor, cost.project):
        raise ValueError("شما اجازه‌ی حذف ندارید.")
    stage = cost.project.stages.order_by("order").first()
    if stage:
        _log(stage, actor, f"هزینه حذف شد: {cost.title} ({cost.amount})")
    cost.delete()


# ---------------- بازبینی نهایی ----------------
def final_review_data(project):
    stages = list(project.stages.prefetch_related(
        "events__actor", Prefetch("files", queryset=ProjectFile.objects.select_related("uploaded_by"))).order_by("order"))
    costs = list(project.recorded_costs.all())
    install = next((s for s in stages if s.kind == StageKind.INSTALL), None)
    undone = []
    if install is not None:
        ticked = set(ServiceTick.objects.filter(stage=install).values_list("service_line_id", flat=True))
        undone = [ps for ps in project.services.select_related("service").order_by("pk") if ps.pk not in ticked]
    return {
        "stages": stages, "costs": costs,
        "totals": {"costs_total": sum((c.amount for c in costs), Decimal(0))},
        "has_install": install is not None, "undone_services": undone,
    }

