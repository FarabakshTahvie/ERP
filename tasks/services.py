import os
from datetime import datetime, time
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from accounts.models import User
from core.capabilities import can
from notifications.models import NotificationType
from utils.line_editor import parse_rows, Col
from utils.jalali_forms import JalaliDateField
from utils.image_utils import optimize_upload, OPTIMIZABLE_EXT
from notifications.services import notify_users
from .models import Task, TaskSubtask, TaskAssignment, TaskSubtaskCheck, TaskAttachment


def parse_subtasks(raw_json):
    if not raw_json:
        return []
    try:
        rows = parse_rows(raw_json, (Col("title", "عنوان زیروظیفه", "text", max_len=255),))
        return [r["title"].strip() for r in rows if r.get("title", "").strip()]
    except Exception:
        raise ValueError("فرمت زیروظایف نامعتبر است.")


def clean_assignees(ids):
    if not ids:
        raise ValueError("حداقل یک مسئول باید انتخاب شود.")
    try:
        user_ids = [int(x) for x in ids if str(x).isdigit()]
    except ValueError:
        raise ValueError("مسئولان نامعتبرند.")
    users = list(User.objects.filter(pk__in=user_ids, is_active=True, role=User.Role.EMPLOYEE))
    if len(users) != len(set(user_ids)):
        raise ValueError("برخی از مسئولان انتخاب‌شده نامعتبر یا غیرفعال‌اند.")
    return users


def build_due(date_raw, hour_raw, minute_raw):
    if not date_raw:
        return None
    try:
        dt = JalaliDateField().clean(date_raw)
        h = int(hour_raw or 17)
        m = int(minute_raw or 0)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
        naive = datetime(dt.year, dt.month, dt.day, h, m)
        return timezone.make_aware(naive)
    except Exception:
        raise ValueError("تاریخ یا ساعت سررسید نامعتبر است.")


@transaction.atomic
def create_task(*, actor, title, description="", due_at=None, subtasks=None, assignee_ids=None):
    if not can(actor, "tasks.manage"):
        raise ValueError("شما دسترسی لازم برای مدیریت وظایف را ندارید.")
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("عنوان وظیفه الزامی و حداکثر ۲۰۰ کاراکتر است.")
    description = (description or "").strip()
    if len(description) > 2000:
        raise ValueError("توضیحات حداکثر ۲۰۰۰ کاراکتر است.")
    
    now = timezone.now()
    if due_at and due_at < now:
        raise ValueError("تاریخ سررسید نمی‌تواند در گذشته باشد.")
    
    users = clean_assignees(assignee_ids)
    subtasks = subtasks or []
    if len(subtasks) > 30:
        raise ValueError("حداکثر ۳۰ زیروظیفه مجاز است.")

    task = Task.objects.create(
        title=title,
        description=description,
        due_at=due_at,
        created_by=actor,
    )

    for idx, st_title in enumerate(subtasks, 1):
        TaskSubtask.objects.create(task=task, title=st_title, order=idx)

    assignments = []
    for u in users:
        assignments.append(TaskAssignment(task=task, user=u))
    TaskAssignment.objects.bulk_create(assignments)

    # ارسال اعلان
    actor_name = actor.get_full_name() or actor.username
    notify_users(
        users,
        notification_type=NotificationType.TASK_ASSIGNED,
        title="وظیفه‌ی جدید",
        body=f"«{title}» از طرف {actor_name}",
        real_target_url="/?tab=my_tasks"
    )

    return task


@transaction.atomic
def update_task(task, *, actor, title, description="", due_at=None, subtasks=None, assignee_ids=None):
    task = Task.objects.select_for_update(of=("self",)).get(pk=task.pk)
    if task.created_by_id != actor.id:
        raise ValueError("شما سازنده‌ی این وظیفه نیستید.")
    
    title = (title or "").strip()
    if not title or len(title) > 200:
        raise ValueError("عنوان وظیفه الزامی و حداکثر ۲۰۰ کاراکتر است.")
    description = (description or "").strip()
    if len(description) > 2000:
        raise ValueError("توضیحات حداکثر ۲۰۰۰ کاراکتر است.")

    now = timezone.now()
    if due_at and due_at < now and due_at != task.due_at:
        raise ValueError("تاریخ سررسید نمی‌تواند در گذشته باشد.")

    users = clean_assignees(assignee_ids)
    subtasks = subtasks or []
    if len(subtasks) > 30:
        raise ValueError("حداکثر ۳۰ زیروظیفه مجاز است.")

    task.title = title
    task.description = description
    task.due_at = due_at
    task.save()

    # همگام‌سازی زیروظایف
    existing_st = {st.title: st for st in task.subtasks.all()}
    new_st_titles = set(subtasks)
    
    # حذف زیروظایف قدیمی که دیگر نیستند
    task.subtasks.exclude(title__in=new_st_titles).delete()

    subtask_added = False
    for idx, st_title in enumerate(subtasks, 1):
        st = existing_st.get(st_title)
        if st:
            st.order = idx
            st.save(update_fields=["order"])
        else:
            TaskSubtask.objects.create(task=task, title=st_title, order=idx)
            subtask_added = True

    # اگر زیروظیفه‌ی تازه اضافه شد، همه‌ی assignmentهای ثبت‌شده باز شوند
    if subtask_added:
        TaskAssignment.objects.filter(task=task).update(submitted_at=None)

    # همگام‌سازی مسئولان
    current_users = {a.user_id: a for a in task.assignments.all()}
    new_user_ids = {u.id for u in users}

    removed_user_ids = set(current_users.keys()) - new_user_ids
    for uid in removed_user_ids:
        ass = current_users[uid]
        if ass.submitted_at is not None:
            raise ValueError(f"مسئول «{ass.user.get_full_name()}» وظیفه را ثبت کرده است و قابل حذف نیست.")
        ass.delete()

    added_users = []
    for u in users:
        if u.id not in current_users:
            TaskAssignment.objects.create(task=task, user=u)
            added_users.append(u)

    if added_users:
        actor_name = actor.get_full_name() or actor.username
        notify_users(
            added_users,
            notification_type=NotificationType.TASK_ASSIGNED,
            title="وظیفه‌ی جدید",
            body=f"«{title}» از طرف {actor_name}",
            real_target_url="/?tab=my_tasks"
        )

    return task


def _own_assignment(task_id, user):
    ass = get_object_or_404(
        TaskAssignment.objects.select_for_update(of=("self",)).select_related("task"),
        task_id=task_id, user=user
    )
    if ass.submitted_at is not None:
        raise ValueError("این وظیفه قبلاً ثبت نهایی شده است.")
    return ass


@transaction.atomic
def set_check(*, task_id, user, subtask_id=None, done=False):
    ass = _own_assignment(task_id, user)
    task = ass.task
    subtasks_count = task.subtasks.count()

    if subtask_id is None:
        # تیک اصلی وظیفه
        if done:
            ass.main_checked = True
            # همه‌ی زیروظایف تیک بخورند
            existing_st_ids = list(task.subtasks.values_list("id", flat=True))
            for st_id in existing_st_ids:
                TaskSubtaskCheck.objects.get_or_create(assignment=ass, subtask_id=st_id)
        else:
            ass.main_checked = False
            TaskSubtaskCheck.objects.filter(assignment=ass).delete()
    else:
        st = get_object_or_404(TaskSubtask, pk=subtask_id, task=task)
        if done:
            TaskSubtaskCheck.objects.get_or_create(assignment=ass, subtask=st)
        else:
            TaskSubtaskCheck.objects.filter(assignment=ass, subtask=st).delete()
        
        # محاسبه main_checked
        checked_count = ass.checks.count()
        ass.main_checked = (subtasks_count > 0 and checked_count == subtasks_count) or (subtasks_count == 0 and done)

    ass.save(update_fields=["main_checked"])
    return {
        "main_checked": ass.main_checked,
        "checked": list(ass.checks.values_list("subtask_id", flat=True)),
        "total": subtasks_count,
    }


@transaction.atomic
def submit_assignment(*, task_id, user, note=""):
    ass = _own_assignment(task_id, user)
    if not ass.main_checked:
        raise ValueError("ابتدا همه‌ی موارد را علامت بزنید.")
    note = (note or "").strip()
    if len(note) > 1000:
        raise ValueError("توضیح حداکثر ۱۰۰۰ کاراکتر است.")
    
    ass.note = note
    ass.submitted_at = timezone.now()
    ass.save(update_fields=["note", "submitted_at"])
    return ass


@transaction.atomic
def add_attachment(task, *, uploaded, actor):
    if task.created_by_id != actor.id:
        raise ValueError("شما سازنده‌ی این وظیفه نیستید.")
    if task.attachments.count() >= 20:
        raise ValueError("حداکثر ۲۰ پیوست مجاز است.")
    if uploaded.size > 25 * 1024 * 1024:
        raise ValueError("حجم فایل بیش از ۲۵ مگابایت است.")

    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "file"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in OPTIMIZABLE_EXT:
        uploaded, changed = optimize_upload(uploaded)
        if changed:
            name = name.rsplit(".", 1)[0] + ".webp"

    return TaskAttachment.objects.create(
        task=task,
        file=uploaded,
        original_name=name,
        uploaded_by=actor,
    )


@transaction.atomic
def delete_attachment(att, actor):
    if att.task.created_by_id != actor.id:
        raise ValueError("شما سازنده‌ی این وظیفه نیستید.")
    att.file.delete(save=False)
    att.delete()
