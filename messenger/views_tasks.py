from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from accounts.models import User
from core.capabilities import can, cap_required
from tasks.models import TaskAssignment
from tasks.views import _assignment_cards
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str

from . import services


def _creator(task):
    u = task.created_by
    return (u.get_full_name() or u.username) if u else "—"


def _employee_only(request):
    return request.user.role == User.Role.EMPLOYEE


def _done_context(request):
    qs = (TaskAssignment.objects.filter(user=request.user, submitted_at__isnull=False)
          .select_related("task__created_by").order_by("-submitted_at"))

    def row_builder(a):
        url = reverse("messenger:task_detail", args=[a.task_id])
        return {"url": url, "cells": [
            {"type": "link", "value": a.task.title, "url": url},
            {"type": "muted", "value": _creator(a.task)},
            {"type": "muted", "value": jalali_str(a.submitted_at, fmt="%Y/%m/%d %H:%M")},
        ]}

    return build_table_context(
        request, qs,
        columns=[{"label": "عنوان", "sort_field": "task__title"}, {"label": "از طرف"},
                 {"label": "زمان ثبت", "sort_field": "submitted_at"}],
        row_builder=row_builder, container_id="table-msgr-tasks-done", param_prefix="mtd_",
        empty_icon="check-square", empty_text="وظیفه‌ی انجام‌شده‌ای نیست.",
        list_url=reverse("messenger:tasks_done_table"),
        search_fields=["task__title"], search_placeholder="جستجو در عنوان...",
    )


@cap_required("messenger.use")
@never_cache
def page_tasks(request):
    if not _employee_only(request):
        return redirect("tasks:list")          # مدیر مسئول وظیفه نمی‌شود؛ فهرست وظایفِ ثبت‌کرده‌اش همان‌جاست
    return render(request, "messenger/tasks.html", {
        "cards": _assignment_cards(request.user, done=False), "is_done_panel": False,
        "inbox": services.inbox(request.user), "done_url": reverse("messenger:tasks_done_table"),
        "can_manage_tasks": can(request.user, "tasks.manage"),
    })


@cap_required("messenger.use")
def done_table(request):
    if not _employee_only(request):
        return redirect("tasks:list")
    return render_table(request, _done_context(request))


@cap_required("messenger.use")
@never_cache
def task_detail(request, task_id):
    if not _employee_only(request):
        return redirect("tasks:list")
    a = get_object_or_404(
        TaskAssignment.objects.select_related("task__created_by")
        .prefetch_related("task__subtasks", "task__attachments", "checks"),
        task_id=task_id, user=request.user)
    checked = {c.subtask_id for c in a.checks.all()}
    return render(request, "messenger/task_detail.html", {
        "a": a, "task": a.task, "creator": _creator(a.task),
        "subtasks": [{"obj": s, "checked": s.pk in checked} for s in a.task.subtasks.all()],
        "attachments": list(a.task.attachments.all()),
    })