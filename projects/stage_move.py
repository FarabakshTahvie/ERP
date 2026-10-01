from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from accounts.models import User
from .models import Project, ProjectStage, StageApproval, StageEvent, StageKind
from .services import EXTERNAL_APPROVAL_TYPES, _assign_stage_responsible

_ACTIVE = (ProjectStage.Status.IN_PROGRESS, ProjectStage.Status.WAITING_APPROVAL)


def can_move_stages(user, project):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == User.Role.ADMIN or project.created_by_id == user.id:
        return True
    if user.role != User.Role.EMPLOYEE:
        return False
    return (
        project.assigned_technicians.filter(pk=user.pk).exists()
        or project.participants.filter(user=user).exists()
        or project.stages.filter(Q(assigned_to=user) | Q(candidate_users=user)).exists()
    )


def _movable_kind(stage):
    t = stage.step_template
    return not (stage.kind == StageKind.PROFORMA or t.requires_payment_selection
                or t.approval_by in EXTERNAL_APPROVAL_TYPES)


def move_options(project):
    """(مرحله‌ی فعلی، [{stage, allowed}]) برای مودال و اعتبارسنجی سرور."""
    stages = list(project.stages.select_related("step_template").order_by("order"))
    parked = {s.return_to_id for s in stages if s.return_to_id}
    current = next((s for s in stages if s.status in _ACTIVE), None)
    options = [{
        "stage": s,
        "allowed": bool(current) and s.pk != current.pk and s.pk not in parked
                   and s.status in (ProjectStage.Status.DONE, ProjectStage.Status.PENDING) and _movable_kind(s),
    } for s in stages]
    return current, options


def _event(stage, actor, old_status, text):
    StageEvent.objects.create(stage=stage, actor=actor, from_status=old_status, to_status=stage.status, comment=text)


@transaction.atomic
def move_to_stage(*, project, target_id, actor, comment):
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("نوشتن توضیح اجباری است.")
    project = Project.objects.select_for_update().get(pk=project.pk)
    if not can_move_stages(actor, project):
        raise ValueError("شما اجازه‌ی انتقال مرحله ندارید.")
    if project.status != Project.Status.IN_PROGRESS:
        raise ValueError("فقط پروژه‌ی در حال اجرا قابل انتقال است.")
    if project.stages.filter(status=ProjectStage.Status.SUSPENDED).exists():
        raise ValueError("پروژه معلق است؛ ابتدا مدیر باید آن را به چرخه برگرداند.")
    current, options = move_options(project)
    option = next((o for o in options if str(o["stage"].pk) == str(target_id)), None)
    if current is None or option is None or not option["allowed"]:
        raise ValueError("این مرحله قابل انتخاب نیست.")

    now = timezone.now()
    origin = ProjectStage.objects.select_for_update().get(pk=current.pk)
    target = ProjectStage.objects.select_for_update().get(pk=option["stage"].pk)

    old = origin.status                     # مرحله‌ی فعلی متوقف می‌شود
    if old == ProjectStage.Status.WAITING_APPROVAL:
        origin.approvals.filter(decision=StageApproval.Decision.PENDING).update(
            decision=StageApproval.Decision.CANCELLED, decided_at=now)
    origin.status = ProjectStage.Status.PENDING
    origin.save(update_fields=["status"])
    _event(origin, actor, old, f"به مرحله‌ی «{target.title}» منتقل شد: {comment}")

    old = target.status                     # مرحله‌ی انتخابی باز می‌شود
    target.status = ProjectStage.Status.IN_PROGRESS
    target.completed_at = target.completed_by = None
    target.started_at = target.started_at or now
    target.return_to = origin
    keep = bool(target.assigned_to_id and target.assigned_to.is_active)
    if not keep:
        target.assigned_to = None
        target.save()
        target.candidate_users.clear()
        _assign_stage_responsible(target)
    target.save()
    _event(target, actor, old, f"از مرحله‌ی «{origin.title}» منتقل شد: {comment}")
    # TODO(اطلاع‌رسانی به مسئول مرحله‌ی بازشده): قالب پیام هنوز آماده نیست.
    return target
