import os
from datetime import datetime

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from accounts.models import User
from core.capabilities import can
from notifications.models import NotificationType
from notifications.services import notify_users
from utils.image_utils import optimize_named
from utils.jalali_forms import JalaliDateField
from utils.line_editor import Col, parse_rows

from .models import Task, TaskAssignment, TaskAttachment, TaskSubtask, TaskSubtaskCheck

MAX_TITLE, MAX_DESC, MAX_NOTE = 200, 2000, 1000
MAX_SUBTASKS, MAX_ATTACHMENTS, MAX_ATTACH_BYTES = 30, 20, 25 * 1024 * 1024
SUBTASK_COLS = (Col("title", "عنوان زیروظیفه", "text", max_len=255),)


def _int_set(ids):
    return {int(x) for x in (ids or []) if str(x).strip().isdigit()}


def parse_subtasks(raw_json):
    """None = ارسال نشده (دست نزن). خروجی: [{"pk": int|None, "title": str}]. خطا = ValueError فارسیِ خود parse_rows."""
    rows = parse_rows(raw_json, SUBTASK_COLS)
    if rows is None:
        return None
    if len(rows) > MAX_SUBTASKS:
        raise ValueError("حداکثر ۳۰ زیروظیفه مجاز است.")
    return [{"pk": r["pk"], "title": r["title"]} for r in rows]


def clean_assignees(ids):
    wanted = _int_set(ids)
    if not wanted:
        raise ValueError("حداقل یک مسئول انتخاب کنید.")
    users = list(User.objects.filter(pk__in=wanted, is_active=True, role=User.Role.EMPLOYEE))
    if len(users) != len(wanted):
        raise ValueError("فقط تکنسین‌های فعال می‌توانند مسئول شوند.")
    return users


def build_due(date_raw, hour_raw, minute_raw):
    if not (date_raw or "").strip():
        return None
    try:
        day = JalaliDateField().clean(date_raw)
        hour, minute = int(hour_raw or 17), int(minute_raw or 0)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return timezone.make_aware(datetime(day.year, day.month, day.day, hour, minute))
    except Exception:
        raise ValueError("تاریخ یا ساعت سررسید نامعتبر است.")


def _clean_texts(title, description):
    title, description = (title or "").strip(), (description or "").strip()
    if not title or len(title) > MAX_TITLE:
        raise ValueError("عنوان وظیفه الزامی و حداکثر ۲۰۰ کاراکتر است.")
    if len(description) > MAX_DESC:
        raise ValueError("توضیحات حداکثر ۲۰۰۰ کاراکتر است.")
    return title, description


def _notify(users, task, actor):
    notify_users(users, notification_type=NotificationType.TASK_ASSIGNED, title="وظیفه‌ی جدید",
                 body=f"«{task.title}» از طرف {actor.get_full_name() or actor.username}",
                 real_target_url="/?tab=my_tasks")


@transaction.atomic
def create_task(*, actor, title, description="", due_at=None, subtasks=None, assignee_ids=None):
    if not can(actor, "tasks.manage"):
        raise ValueError("شما اجازه‌ی ثبت وظیفه ندارید.")
    title, description = _clean_texts(title, description)
    if due_at and due_at < timezone.now():
        raise ValueError("ددلاین نمی‌تواند در گذشته باشد.")
    users = clean_assignees(assignee_ids)
    task = Task.objects.create(title=title, description=description, due_at=due_at, created_by=actor)
    TaskSubtask.objects.bulk_create([TaskSubtask(task=task, title=s["title"], order=i)
                                     for i, s in enumerate(subtasks or [], 1)])
    TaskAssignment.objects.bulk_create([TaskAssignment(task=task, user=u) for u in users])
    _notify(users, task, actor)
    return task


def _sync_subtasks(task, rows):
    """همگام با pk (فقط زیروظیفه‌های همین وظیفه). خروجی: True اگر زیروظیفه‌ی تازه اضافه شد."""
    existing = {s.pk: s for s in task.subtasks.all()}
    keep, added = set(), False
    for order, row in enumerate(rows, 1):
        st = existing.get(row["pk"]) if row["pk"] and row["pk"] not in keep else None
        if st is None:
            st, added = TaskSubtask(task=task), True
        st.title, st.order = row["title"], order
        st.save()
        keep.add(st.pk)
    task.subtasks.exclude(pk__in=keep).delete()          # تیک‌هایشان cascade می‌رود
    return added


def _sync_assignees(task, wanted, new_users, actor):
    current = {a.user_id: a for a in task.assignments.select_related("user")}
    removed = set(current) - wanted
    for uid in removed:
        if current[uid].submitted_at is not None:
            raise ValueError(f"«{current[uid].user.get_full_name() or current[uid].user.username}» "
                             "وظیفه را ثبت کرده و قابل حذف نیست.")
    TaskAssignment.objects.filter(task=task, user_id__in=removed).delete()
    TaskAssignment.objects.bulk_create([TaskAssignment(task=task, user=u) for u in new_users])
    if new_users:
        _notify(new_users, task, actor)


def _recompute_main(task):
    total = task.subtasks.count()
    if not total:
        return
    for a in task.assignments.annotate(n=Count("checks")):
        full = a.n == total
        if a.main_checked != full:
            a.main_checked = full
            a.save(update_fields=["main_checked"])


@transaction.atomic
def update_task(task, *, actor, title, description="", due_at=None, subtasks=None, assignee_ids=None):
    """subtasks=None یعنی دست نزن؛ [] یعنی همه را پاک کن."""
    task = Task.objects.select_for_update(of=("self",)).get(pk=task.pk)
    if task.created_by_id != actor.id or not can(actor, "tasks.manage"):
        raise ValueError("فقط سازنده‌ی وظیفه می‌تواند آن را ویرایش کند.")
    title, description = _clean_texts(title, description)
    if due_at and due_at != task.due_at and due_at < timezone.now():
        raise ValueError("ددلاین نمی‌تواند در گذشته باشد.")
    existing_ids = set(task.assignments.values_list("user_id", flat=True))
    wanted = _int_set(assignee_ids)
    if not wanted:
        raise ValueError("حداقل یک مسئول انتخاب کنید.")
    new_users = clean_assignees(wanted - existing_ids) if wanted - existing_ids else []   # قدیمی‌ها دوباره اعتبارسنجی نمی‌شوند

    task.title, task.description, task.due_at = title, description, due_at
    task.save()
    reopen = _sync_subtasks(task, subtasks) if subtasks is not None else False
    _sync_assignees(task, wanted, new_users, actor)
    if reopen:   # زیروظیفه‌ی تازه: همه‌ی مسئولان دوباره باز می‌شوند
        TaskAssignment.objects.filter(task=task).update(submitted_at=None, main_checked=False)
    _recompute_main(task)
    return task


def _own_assignment(task_id, user):
    ass = (TaskAssignment.objects.select_for_update(of=("self",)).select_related("task")
           .filter(task_id=task_id, user=user).first())
    if ass is None:
        raise ValueError("این وظیفه به شما سپرده نشده است.")
    if ass.submitted_at is not None:
        raise ValueError("این وظیفه را قبلاً ثبت کرده‌اید.")
    return ass


@transaction.atomic
def set_check(*, task_id, user, subtask_id=None, done=False):
    ass = _own_assignment(task_id, user)
    ids = list(ass.task.subtasks.values_list("pk", flat=True))
    if subtask_id is None:                                   # تیک وظیفه‌ی اصلی
        ass.checks.all().delete()
        if done:
            TaskSubtaskCheck.objects.bulk_create([TaskSubtaskCheck(assignment=ass, subtask_id=i) for i in ids])
        ass.main_checked = bool(done)
    else:
        if subtask_id not in ids:
            raise ValueError("زیروظیفه‌ی نامعتبر است.")
        if done:
            TaskSubtaskCheck.objects.get_or_create(assignment=ass, subtask_id=subtask_id)
        else:
            ass.checks.filter(subtask_id=subtask_id).delete()
        ass.main_checked = ass.checks.count() == len(ids)
    ass.save(update_fields=["main_checked"])
    return {"main_checked": ass.main_checked, "total": len(ids),
            "checked": list(ass.checks.values_list("subtask_id", flat=True))}


@transaction.atomic
def submit_assignment(*, task_id, user, note=""):
    ass = _own_assignment(task_id, user)
    if not ass.main_checked:
        raise ValueError("ابتدا همه‌ی موارد را علامت بزنید.")
    note = (note or "").strip()
    if len(note) > MAX_NOTE:
        raise ValueError("توضیح حداکثر ۱۰۰۰ کاراکتر است.")
    ass.note, ass.submitted_at = note, timezone.now()
    ass.save(update_fields=["note", "submitted_at"])
    return ass


@transaction.atomic
def add_attachment(task, *, uploaded, actor):
    if task.created_by_id != actor.id or not can(actor, "tasks.manage"):
        raise ValueError("فقط سازنده‌ی وظیفه می‌تواند پیوست بگذارد.")
    if task.attachments.count() >= MAX_ATTACHMENTS:
        raise ValueError("حداکثر ۲۰ پیوست برای هر وظیفه مجاز است.")
    if uploaded.size > MAX_ATTACH_BYTES:
        raise ValueError("حجم فایل بیش از ۲۵ مگابایت است.")
    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "file"
    uploaded, name = optimize_named(uploaded, name)
    return TaskAttachment.objects.create(task=task, file=uploaded, original_name=name, uploaded_by=actor)


@transaction.atomic
def delete_attachment(att, actor):
    if att.task.created_by_id != actor.id:
        raise ValueError("فقط سازنده‌ی وظیفه می‌تواند پیوست را حذف کند.")
    att.file.delete(save=False)
    att.delete()
