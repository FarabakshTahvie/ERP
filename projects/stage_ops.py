import os
import uuid
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from accounts.models import User
from utils.image_utils import optimize_named
from utils.utils import guess_file_kind
from .models import FileGroup, Project, ProjectFile, ProjectStage, StageKind
from .services import advance_stage, user_is_accountant

MAX_STAGE_FILES = 200
MAX_FILE_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx
MAX_CUTS = 999
GROUP_TITLE_MAX = 100
MAX_GROUPS = 50
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


from core.capabilities import is_manager as _is_manager


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


VOICE_MAX_BYTES = 12 * 1024 * 1024
VOICE_MAX_SECONDS = 300
VOICE_ONLY_COMMENT = "پیام صوتی"


def _voice_ext(head):
    """پسوند از فرمت واقعی فایل (نه نام آن)."""
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if head[:4] == b"OggS":
        return "ogg"
    if head[4:8] == b"ftyp":
        return "m4a"
    return None


def _clean_peaks(raw):
    parts = [p for p in str(raw or "").split(",") if p.strip()]
    try:
        values = [int(p) for p in parts]
    except ValueError:
        return ""
    if not (8 <= len(values) <= 64) or any(v < 0 or v > 100 for v in values):
        return ""
    return ",".join(str(v) for v in values)


def prepare_voice(uploaded, duration_raw, peaks_raw):
    """None اگر صدایی نیست؛ وگرنه dict آماده‌ی StageEvent. هر ایرادی ValueError فارسی."""
    if not uploaded:
        return None
    if uploaded.size > VOICE_MAX_BYTES:
        raise ValueError("حجم پیام صوتی بیشتر از حد مجاز است.")
    head = uploaded.read(12)
    uploaded.seek(0)
    ext = _voice_ext(head)
    if not ext:
        raise ValueError("فایل صوتی معتبر نیست.")
    try:
        duration = int(str(duration_raw or "").translate(_FA_TO_EN).strip())
    except ValueError:
        raise ValueError("مدت پیام صوتی نامعتبر است.")
    if not (1 <= duration <= VOICE_MAX_SECONDS + 5):
        raise ValueError("مدت پیام صوتی نامعتبر است (حداکثر ۵ دقیقه).")
    uploaded.name = f"{uuid.uuid4().hex}.{ext}"
    return {"voice": uploaded, "voice_duration": min(duration, VOICE_MAX_SECONDS),
            "voice_peaks": _clean_peaks(peaks_raw)}


def _group_for(stage, raw):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    group = FileGroup.objects.filter(pk=int(text), stage=stage).first() if text.isdigit() else None
    if group is None:
        raise ValueError("ابتدا گروه (مثلاً طبقه‌ی اول) را بسازید یا انتخاب کنید.")
    return group


def add_stage_file(*, stage, uploaded, uploader, cut_count_raw=None, group_id=None):
    if stage.project.status == Project.Status.CANCELLED:
        raise ValueError("این پروژه لغو شده است.")
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
        group = _group_for(locked, group_id) if stage.kind == StageKind.GCODE else None
        uploaded, name = optimize_named(uploaded, name)
        created = ProjectFile.objects.create(
            stage=stage, file=uploaded, kind=guess_file_kind(name), original_name=name,
            uploaded_by=uploader, is_attachment=True, cut_count=cut_count, group=group,
        )
        if group is not None and group.cut_done:   # فایل تازه آمد؛ تیک «انجام شد» گروه دیگر درست نیست
            FileGroup.objects.filter(pk=group.pk).update(cut_done=False, cut_done_by=None, cut_done_at=None)
        return created


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
            .order_by("created_at", "pk"))


def _with_files(qs):
    files = ProjectFile.objects.select_related("uploaded_by").order_by("created_at", "pk")
    groups = list(qs.select_related("cut_done_by").prefetch_related(
        Prefetch("files", queryset=files, to_attr="file_list")))
    for g in groups:
        g.cut_total = sum((f.cut_count or 0) for f in g.file_list)
    return groups


def project_groups(project):
    """همه‌ی گروه‌های جی‌کد پروژه (حتی خالی)؛ هر کدام file_list و cut_total دارد."""
    return _with_files(FileGroup.objects.filter(project=project).order_by("created_at", "pk"))


def cut_groups(project):
    """گروه‌هایی که فایل جی‌کد با تعداد برش دارند؛ گروه خالی نمی‌آید."""
    return [g for g in project_groups(project) if any(f.cut_count for f in g.file_list)]


def groups_progress(project):
    """(کل گروه‌ها، گروه‌های انجام‌شده) برای برش‌کاری"""
    groups = cut_groups(project)
    return len(groups), sum(1 for g in groups if g.cut_done)


@transaction.atomic
def create_group(*, stage, title, actor):
    locked = ProjectStage.objects.select_for_update(of=("self",)).select_related("project").get(pk=stage.pk)
    if locked.kind != StageKind.GCODE:
        raise ValueError("گروه‌بندی فقط برای مرحله‌ی جی‌کدگیری است.")
    if locked.project.status == Project.Status.CANCELLED:
        raise ValueError("این پروژه لغو شده است.")
    if not can_upload_to_stage(actor, locked):
        raise ValueError("شما اجازه‌ی ساخت گروه در این مرحله را ندارید.")
    if locked.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("گروه فقط در مرحله‌ی «در حال انجام» ساخته می‌شود.")
    name = " ".join(str(title or "").split())
    if not name:
        raise ValueError("نام گروه را بنویسید.")
    if len(name) > GROUP_TITLE_MAX:
        raise ValueError(f"نام گروه نباید بیش از {GROUP_TITLE_MAX} نویسه باشد.")
    existing = list(locked.file_groups.values_list("title", flat=True))
    if len(existing) >= MAX_GROUPS:
        raise ValueError(f"حداکثر {MAX_GROUPS} گروه مجاز است.")
    key = name.translate(_FA_TO_EN).casefold()
    if any(t.translate(_FA_TO_EN).casefold() == key for t in existing):
        raise ValueError("گروهی با این نام قبلاً ساخته شده است.")
    return FileGroup.objects.create(project=locked.project, stage=locked, title=name, created_by=actor)


@transaction.atomic
def set_group_cut_done(*, group, done, actor):
    """صریح و idempotent (نه toggle): «انجام شد» را روشن یا خاموش می‌کند."""
    group = FileGroup.objects.select_for_update(of=("self",)).select_related("project").get(pk=group.pk)
    if group.project.status == Project.Status.CANCELLED:
        raise ValueError("این پروژه لغو شده است.")
    cutting = group.project.stages.filter(kind=StageKind.CUTTING).first()
    if cutting is None or cutting.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("مرحله‌ی برش‌کاری فعال نیست.")
    if not can_upload_to_stage(actor, cutting):
        raise ValueError("شما اجازه‌ی ثبت برش را ندارید.")
    if not group.files.filter(cut_count__gt=0).exists():
        raise ValueError("این گروه فایلی با تعداد برش ندارد.")
    done = bool(done)
    if group.cut_done == done:
        return group
    group.cut_done = done
    group.cut_done_by = actor if done else None
    group.cut_done_at = timezone.now() if done else None
    group.save(update_fields=["cut_done", "cut_done_by", "cut_done_at", "updated_at"])
    return group


def stage_completion_problem(stage, *, show_to_client=False):
    """پیام خطا یا None. تنها منبع شرط‌های تکمیل."""
    need = upload_requirement(stage)
    files = stage.files.all()
    if need == "any" and not files.exists():
        return "برای تکمیل این مرحله حداقل یک فایل ارسال کنید."
    if need == "image" and not files.filter(kind=ProjectFile.Kind.IMAGE).exists():
        return "برای تکمیل این مرحله حداقل یک عکس ارسال کنید."
    if stage.kind == StageKind.GCODE and files.filter(group__isnull=True).exists():
        return "هر فایل جی‌کد باید داخل یک گروه (مثلاً طبقه‌ی اول) باشد."
    if stage.kind == StageKind.CUTTING:
        total, done = groups_progress(stage.project)
        if total == 0:
            return "گروهی با فایل جی‌کد برای این پروژه ثبت نشده است."
        if done < total:
            return f"هنوز {total - done} گروه از {total} گروه «انجام شد» نخورده است."
    if stage.kind == StageKind.DESIGN_INITIAL and show_to_client and not files.filter(
            kind__in=(ProjectFile.Kind.PDF, ProjectFile.Kind.IMAGE)).exists():
        return "برای نمایش به مشتری، حداقل یک عکس یا PDF از طرح بارگذاری کنید تا مشتری بتواند بدون نرم‌افزار ببیند."
    return None


@transaction.atomic
def complete_stage(*, stage, actor, comment, show_to_client=False, via_review=False, voice=None):
    stage = ProjectStage.objects.select_for_update(of=("self",)).select_related("step_template", "project").get(pk=stage.pk)
    if stage.kind == StageKind.PROFORMA:
        raise ValueError("این مرحله فقط با «صدور پیش‌فاکتور» از صفحه‌ی ویرایشگر تکمیل می‌شود.")
    if stage.kind == StageKind.FINAL_REVIEW and not via_review:
        raise ValueError("بازبینی نهایی فقط از صفحه‌ی «بازبینی نهایی» تایید می‌شود.")
    if stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("این مرحله در حال انجام نیست.")
    if (actor.role == User.Role.EMPLOYEE and stage.assigned_to_id != actor.id
            and not (stage.kind == StageKind.FINAL_REVIEW and user_is_accountant(actor))):
        raise ValueError("ابتدا این کار را برای خودتان بردارید.")
    problem = stage_completion_problem(stage, show_to_client=show_to_client)
    if problem:
        raise ValueError(problem)

    comment = (comment or "").strip()
    if voice and not comment:
        comment = VOICE_ONLY_COMMENT
    note = comment
    if stage.kind == StageKind.DESIGN_INITIAL:
        stage.client_preview = bool(show_to_client)
        stage.save(update_fields=["client_preview", "updated_at"])
        note = f"{comment}\n[{'طرح برای مشتری نمایش داده می‌شود' if show_to_client else 'طرح برای مشتری نمایش داده نمی‌شود'}]"
    return advance_stage(stage, actor=actor, new_status=ProjectStage.Status.DONE, comment=note, voice=voice)
