import os
from django.db import IntegrityError, transaction
from django.utils import timezone
from accounts.models import User
from utils.utils import guess_file_kind
from .models import CutDone, ProjectFile, ProjectStage, StageEvent, StageKind
from .services import advance_stage, user_is_accountant

MAX_STAGE_FILES = 200
MAX_FILE_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx
MAX_CUTS = 999
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _is_manager(user):
    return user.is_superuser or user.role == User.Role.ADMIN


def can_upload_to_stage(user, stage):
    """مسئول مرحله، ثبت‌کننده‌ی پروژه یا مدیر."""
    return user.is_authenticated and (
        _is_manager(user) or stage.assigned_to_id == user.id or stage.project.created_by_id == user.id
    )


def parse_cut_count(raw):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    if not text.isdigit() or not (1 <= int(text) <= MAX_CUTS):
        raise ValueError(f"تعداد برش باید عددی صحیح بین ۱ تا {MAX_CUTS} باشد.")
    return int(text)


def add_stage_file(*, stage, uploaded, uploader, cut_count_raw=None):
    if not can_upload_to_stage(uploader, stage):
        raise ValueError("شما اجازه‌ی ارسال فایل در این مرحله را ندارید.")
    if uploaded is None:
        raise ValueError("فایلی ارسال نشده است.")
    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "file"
    if uploaded.size > MAX_FILE_BYTES:
        raise ValueError(f"حجم «{name}» بیشتر از ۲۵ مگابایت است.")
    cut_count = parse_cut_count(cut_count_raw) if stage.kind == StageKind.GCODE else None
    with transaction.atomic():
        locked = ProjectStage.objects.select_for_update().get(pk=stage.pk)   # چک سقف و وضعیت پشت قفل
        if locked.status != ProjectStage.Status.IN_PROGRESS:
            raise ValueError("فایل فقط در مرحله‌ی «در حال انجام» قابل ارسال است.")
        if locked.files.count() >= MAX_STAGE_FILES:
            raise ValueError(f"حداکثر {MAX_STAGE_FILES} فایل برای هر مرحله مجاز است.")
        return ProjectFile.objects.create(
            stage=stage, file=uploaded, kind=guess_file_kind(name), original_name=name,
            uploaded_by=uploader, is_attachment=True, cut_count=cut_count,
        )


def upload_requirement(stage):
    """None | 'any' | 'image'"""
    if stage.kind in (StageKind.SHIPPING, StageKind.INSTALL):
        return "image"
    if stage.kind in (StageKind.DESIGN_INITIAL, StageKind.GCODE):
        return "any"
    if stage.kind == StageKind.GENERIC and stage.step_template and stage.step_template.allows_file_upload:
        return "any"
    return None


def cut_files(project):
    return (ProjectFile.objects.filter(stage__project=project, stage__kind=StageKind.GCODE, cut_count__gt=0)
            .prefetch_related("cuts_done").order_by("created_at", "pk"))


def cuts_summary(project):
    """(کل برش‌ها، برش‌های انجام‌شده)"""
    total = done = 0
    for f in cut_files(project):
        total += f.cut_count
        done += len({c.index for c in f.cuts_done.all() if 1 <= c.index <= f.cut_count})
    return total, done


def set_cut(*, file, index, done, actor):
    """صریح و idempotent (نه toggle): دو کلیک پشت‌سرهم نتیجه‌ی مبهم نمی‌دهد."""
    cutting = file.stage.project.stages.filter(kind=StageKind.CUTTING).first()
    if cutting is None or cutting.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("مرحله‌ی برش‌کاری فعال نیست.")
    if not can_upload_to_stage(actor, cutting):
        raise ValueError("شما اجازه‌ی ثبت برش را ندارید.")
    if file.stage.kind != StageKind.GCODE or not file.cut_count or not (1 <= index <= file.cut_count):
        raise ValueError("شماره‌ی برش نامعتبر است.")
    if done:
        try:
            with transaction.atomic():
                CutDone.objects.get_or_create(file=file, index=index, defaults={"done_by": actor})
        except IntegrityError:
            pass
    else:
        CutDone.objects.filter(file=file, index=index).delete()


def stage_completion_problem(stage, *, needs_approval=None):
    """پیام خطا یا None. تنها منبع شرط‌های تکمیل؛ فاز ۳ چک‌لیست‌های ارسال و نصب را همین‌جا اضافه می‌کند."""
    need = upload_requirement(stage)
    files = stage.files.all()
    if need == "any" and not files.exists():
        return "برای تکمیل این مرحله حداقل یک فایل ارسال کنید."
    if need == "image" and not files.filter(kind=ProjectFile.Kind.IMAGE).exists():
        return "برای تکمیل این مرحله حداقل یک عکس ارسال کنید."
    if stage.kind == StageKind.CUTTING:
        total, done = cuts_summary(stage.project)
        if total == 0:
            return "فایل جی‌کدی با تعداد برش برای این پروژه ثبت نشده است."
        if done < total:
            return f"هنوز {total - done} برش از {total} برش علامت نخورده است."
    if stage.kind == StageKind.DESIGN_INITIAL and needs_approval is None and not stage.return_to_id:
        return "مشخص کنید این طرح نیاز به تایید مشتری دارد یا نه."
    from . import ops
    if stage.kind == StageKind.SHIPPING:
        problem = ops.shipping_problem(stage)
        if problem:
            return problem
    if stage.kind == StageKind.INSTALL:
        problem = ops.install_problem(stage)
        if problem:
            return problem
    if stage.kind == StageKind.FINAL_REVIEW and ops.pending_part_requests(stage.project).exists():
        return "درخواست قطعه‌ی بررسی‌نشده دارید؛ ابتدا تکلیفش روشن شود."
    return None


@transaction.atomic
def complete_stage(*, stage, actor, comment, needs_approval=None, via_review=False):
    stage = ProjectStage.objects.select_for_update().select_related("step_template", "project").get(pk=stage.pk)
    if stage.kind == StageKind.PROFORMA:
        raise ValueError("این مرحله فقط با «صدور پیش‌فاکتور» از صفحه‌ی ویرایشگر تکمیل می‌شود.")
    if stage.kind == StageKind.FINAL_REVIEW and not via_review:
        raise ValueError("بازبینی نهایی فقط از صفحه‌ی «بازبینی نهایی» تایید می‌شود.")
    if stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("این مرحله در حال انجام نیست.")
    if (actor.role == User.Role.EMPLOYEE and stage.assigned_to_id != actor.id
            and not (stage.kind == StageKind.FINAL_REVIEW and user_is_accountant(actor))):
        raise ValueError("ابتدا این کار را برای خودتان بردارید.")
    problem = stage_completion_problem(stage, needs_approval=needs_approval)
    if problem:
        raise ValueError(problem)

    note = comment
    if stage.kind == StageKind.DESIGN_INITIAL and not stage.return_to_id:
        note = f"{comment}\n[{'نیاز به تایید مشتری دارد' if needs_approval else 'بدون نیاز به تایید مشتری'}]"
        if not needs_approval:
            approval = stage.project.stages.filter(
                kind=StageKind.DESIGN_APPROVAL, order__gt=stage.order,
                status__in=(ProjectStage.Status.PENDING, ProjectStage.Status.REJECTED),
            ).order_by("order").first()
            if approval:   # قبل از تمام‌کردن طراحی: advance_stage مرحله‌ی بعدیِ «انجام‌نشده» را فعال می‌کند
                old = approval.status
                approval.status = ProjectStage.Status.DONE
                approval.completed_at, approval.completed_by = timezone.now(), actor
                approval.client_visible = False
                approval.save()
                StageEvent.objects.create(
                    stage=approval, actor=actor, from_status=old, to_status=approval.status,
                    comment="بدون نیاز به تایید مشتری (تصمیم طراح)")
    return advance_stage(stage, actor=actor, new_status=ProjectStage.Status.DONE, comment=note)
