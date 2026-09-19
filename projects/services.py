from django.db import transaction
from django.utils import timezone

from .models import ProjectStage, StageEvent


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
            client_visible=step.client_visible,
            status=ProjectStage.Status.PENDING,
        )
        for step in steps
    ]
    ProjectStage.objects.bulk_create(stages)

    first_stage = project.stages.order_by("order").first()
    if first_stage:
        first_stage.status = ProjectStage.Status.IN_PROGRESS
        first_stage.started_at = timezone.now()
        first_stage.save(update_fields=["status", "started_at"])
    return list(project.stages.order_by("order"))


@transaction.atomic
def advance_stage(stage, actor, new_status, comment):
    if not comment or not comment.strip():
        raise ValueError("ثبت توضیح برای این مرحله اجباری است.")

    from accounts.models import User
    if getattr(actor, "role", None) == User.Role.EMPLOYEE and stage.assigned_to_id and stage.assigned_to_id != actor.id:
        raise ValueError("فقط مسئول این مرحله می‌تواند وضعیتش را تغییر دهد.")

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
        _activate_next_stage(stage)

    return stage


def _activate_next_stage(stage):
    next_stage = (
        stage.project.stages.filter(order__gt=stage.order, status=ProjectStage.Status.PENDING)
        .order_by("order").first()
    )
    if not next_stage:
        return
    next_stage.status = ProjectStage.Status.IN_PROGRESS
    next_stage.started_at = timezone.now()

    template = next_stage.step_template
    notify_users = []

    if template.default_assignee_id:
        # اولویت ۱: مسئول از قبل مشخص‌شده
        next_stage.assigned_to = template.default_assignee
        notify_users = [template.default_assignee]

    elif template.responsible_specialty_id:
        # اولویت ۲: استخر تکنسین‌های همان تخصص — کسی که زودتر Claim کند مسئول می‌شود
        from accounts.models import User
        candidates = list(User.objects.filter(
            role=User.Role.EMPLOYEE, specialties=template.responsible_specialty, is_active=True,
        ))
        next_stage.save()  # اول ذخیره تا candidate_users قابل ست‌شدن باشد
        next_stage.candidate_users.set(candidates)
        notify_users = candidates

    elif template.responsible_role:
        # اولویت ۳: کل یک نقش (مثلاً همه‌ی مدیران)
        from accounts.models import User
        notify_users = list(User.objects.filter(role=template.responsible_role, is_active=True))

    next_stage.save()

    # TODO(نوتیفیکیشن ارجاع کار): وقتی محتوا/تنظیمات پوش نهایی و تایید شد این بخش را از کامنت خارج کن.
    # from notifications.services import create_notification
    # from notifications.models import NotificationType
    # for user in notify_users:
    #     create_notification(
    #         notification_type=NotificationType.MANUAL,
    #         user=user,
    #         title="ارجاع کار جدید",
    #         body=f"مرحله «{next_stage.title}» از پروژه «{stage.project.name}» به شما ارجاع شد.",
    #     )


@transaction.atomic
def claim_stage(stage, user):
    """کاربری که در candidate_users هست (یا ادمین) این کار را رسماً برمی‌دارد."""
    from accounts.models import User
    if stage.assigned_to_id:
        raise ValueError("این مرحله قبلاً به شخص دیگری اختصاص یافته است.")
    if user.role != User.Role.ADMIN and not stage.candidate_users.filter(pk=user.pk).exists():
        raise ValueError("شما جزو افراد واجد شرایط این مرحله نیستید.")
    stage.assigned_to = user
    stage.candidate_users.clear()
    stage.save(update_fields=["assigned_to"])
    StageEvent.objects.create(stage=stage, actor=user, from_status=stage.status, to_status=stage.status, comment="کار توسط این شخص برداشته شد (Claim).")
    return stage


def default_approval_party(project):
    if project.owner_id and not project.partner_id:
        return project.owner
    return project.partner  # پیش‌فرض همیشه شریک تجاری وقتی هر دو موجودند یا فقط شریک موجود است


@transaction.atomic
def resume_suspended_stage(stage, actor, comment):
    if not comment or not comment.strip():
        raise ValueError("ثبت دلیل بازگشت به چرخه اجباری است.")
    old = stage.status
    stage.status = ProjectStage.Status.IN_PROGRESS
    stage.save(update_fields=["status"])
    StageEvent.objects.create(stage=stage, actor=actor, from_status=old, to_status=stage.status, comment=comment)


@transaction.atomic
def cancel_project_from_stage(stage, actor, comment):
    if not comment or not comment.strip():
        raise ValueError("ثبت دلیل لغو پروژه اجباری است.")
    project = stage.project
    from .models import Project
    project.status = Project.Status.CANCELLED
    project.save(update_fields=["status"])
    old = stage.status
    stage.status = ProjectStage.Status.REJECTED
    stage.save(update_fields=["status"])
    StageEvent.objects.create(stage=stage, actor=actor, from_status=old, to_status=stage.status, comment=f"پروژه لغو شد: {comment}")


@transaction.atomic
def assign_stage(stage, target_user, actor, comment):
    from accounts.models import User
    if not (actor.is_superuser or actor.role == User.Role.ADMIN):
        raise ValueError("فقط مدیر می‌تواند مرحله را آزادانه به هرکسی ارجاع دهد.")
    if not comment or not comment.strip():
        raise ValueError("ثبت دلیل ارجاع دستی اجباری است.")
    stage.assigned_to = target_user
    stage.candidate_users.clear()
    stage.save(update_fields=["assigned_to"])
    StageEvent.objects.create(stage=stage, actor=actor, from_status=stage.status, to_status=stage.status, comment=comment)
    return stage


@transaction.atomic
def send_stage_for_approval(stage, party=None, sent_by=None):
    """ثبت درخواست تاییدیه؛ ارسال واقعی پوش/پیامک فعلاً کامنت."""
    if not party:
        party = default_approval_party(stage.project)
    from .models import StageApproval
    approval = StageApproval.objects.create(stage=stage, sent_to_party=party, sent_by=sent_by)
    stage.status = ProjectStage.Status.WAITING_APPROVAL
    stage.save(update_fields=["status"])

    # TODO(پوش سپس پیامک ۱۵دقیقه‌ای برای تاییدیه): وقتی آماده شد از کامنت خارج شود.
    # این جریان دقیقاً همان چیزی‌ست که NotificationPolicy با channel_policy=PUSH_THEN_SMS_FALLBACK
    # و کرون process_notification_fallbacks از قبل پشتیبانی می‌کند؛ فقط باید
    # NotificationType.STAGE_APPROVAL_REQUEST اضافه و پالیسی‌اش در پنل تنظیم شود.
    # user = party.users.first()
    # if user:
    #     from notifications.services import create_notification
    #     from notifications.models import NotificationType
    #     create_notification(
    #         notification_type=NotificationType.STAGE_APPROVAL_REQUEST,
    #         user=user,
    #         title="نیاز به تایید شما",
    #         body=f"مرحله «{stage.client_label or stage.title}» نیاز به تایید شما دارد.",
    #         real_target_url=f"/portal/projects/{stage.project_id}/approve/{approval.id}/",
    #     )
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
