from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from core.capabilities import can, cap_required
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits
from utils.tabs import build_tabs_context

from . import services
from .models import Task, TaskAssignment, TaskAttachment


def _creator_task_or_404(request, task_id, *, deep=False):
    qs = Task.objects.filter(created_by=request.user)
    if deep:
        qs = qs.select_related("created_by").prefetch_related("subtasks", "attachments", "assignments__user",
                                                                "assignments__checks")
    return get_object_or_404(qs, pk=task_id)


def _technician_options():
    users = (User.objects.filter(is_active=True, role=User.Role.EMPLOYEE).prefetch_related("specialties")
             .order_by("last_name", "first_name", "username"))
    return [{"id": u.pk, "name": u.get_full_name() or u.username,
             "sub": "، ".join(s.name for s in u.specialties.all())} for u in users]


def _form_context(task=None):
    local = timezone.localtime(task.due_at) if task and task.due_at else None
    return {
        "task": task,
        "technician_options": _technician_options(),
        "hour_choices": [f"{h:02d}" for h in range(24)],
        "minute_choices": [f"{m:02d}" for m in range(0, 60, 5)],
        "due_date_value": jalali_str(local, fmt="%Y/%m/%d") if local else "",
        "due_hour_value": f"{local.hour:02d}" if local else "17",
        "due_minute_value": f"{local.minute - local.minute % 5:02d}" if local else "00",
        "subtasks_initial": [{"pk": s.pk, "title": s.title} for s in task.subtasks.all()] if task else [],
        "assignee_initial": [{"id": a.user_id, "name": a.user.get_full_name() or a.user.username}
                             for a in task.assignments.select_related("user")] if task else [],
        "attachments": list(task.attachments.all()) if task else [],
    }


# ---------- لیست مدیر/حسابدار ----------
def _tasks_qs(user, *, done):
    qs = (Task.objects.filter(created_by=user)
          .annotate(n_total=Count("assignments", distinct=True),
                    n_done=Count("assignments", filter=Q(assignments__submitted_at__isnull=False), distinct=True),
                    finished_at=Max("assignments__submitted_at")))
    if done:
        return qs.filter(n_total__gt=0, n_done=F("n_total"))
    return qs.filter(Q(n_total=0) | Q(n_done__lt=F("n_total")))


def _table_context(request, *, done):
    now = timezone.now()
    qs = _tasks_qs(request.user, done=done).prefetch_related("assignments__user")

    def row_builder(t):
        who = [a.user.get_full_name() or a.user.username for a in t.assignments.all()]
        who_text = "، ".join(who[:3]) + (to_fa_digits(f" و {len(who) - 3} نفر دیگر") if len(who) > 3 else "")
        progress = to_fa_digits(f"{t.n_done} از {t.n_total} نفر ثبت کرده‌اند")
        edit = {"type": "actions", "actions": [{"url": reverse("tasks:edit", args=[t.id]), "label": "ویرایش"}]}
        if done:
            cells = [{"type": "text", "value": t.title}, {"type": "text", "value": who_text},
                     {"type": "text", "value": progress},
                     {"type": "muted", "value": jalali_str(t.finished_at, fmt="%Y/%m/%d %H:%M") if t.finished_at else "—"},
                     edit]
        else:
            overdue = bool(t.due_at and t.due_at < now)
            cells = [{"type": "text", "value": t.title},
                     {"type": "muted", "value": jalali_str(t.due_at, fmt="%Y/%m/%d %H:%M") if t.due_at else "بدون ددلاین"},
                     {"type": "text", "value": who_text}, {"type": "text", "value": progress},
                     {"type": "badge", "value": "ددلاین گذشته" if overdue else "در جریان",
                      "variant": "error" if overdue else "info"}, edit]
        return {"url": reverse("tasks:detail", args=[t.id]), "cells": cells}

    if done:
        columns = [{"label": "عنوان", "sort_field": "title"}, {"label": "مسئولان"}, {"label": "پیشرفت"},
                   {"label": "تاریخ ثبت نهایی", "sort_field": "finished_at"}, {"label": "عملیات"}]
    else:
        columns = [{"label": "عنوان", "sort_field": "title"}, {"label": "ددلاین", "sort_field": "due_at"},
                   {"label": "مسئولان"}, {"label": "پیشرفت"}, {"label": "وضعیت"}, {"label": "عملیات"}]
    return build_table_context(
        request, qs, columns=columns, row_builder=row_builder,
        container_id="table-tasks-done" if done else "table-tasks-open",
        param_prefix="tkd_" if done else "tko_",
        empty_icon="check-square",
        empty_text="وظیفه‌ی انجام‌شده‌ای نیست." if done else "وظیفه‌ی در جریانی نیست.",
        list_url=reverse("tasks:done_table" if done else "tasks:open_table"),
        search_fields=["title", "assignments__user__first_name", "assignments__user__last_name",
                       "assignments__user__username"],
        search_placeholder="جستجو در عنوان یا نام مسئول...",
    )


@cap_required("tasks.manage")
def task_list(request):
    open_ctx, done_ctx = _table_context(request, done=False), _table_context(request, done=True)
    tabs = build_tabs_context(request, [
        {"key": "open", "label": "وظایف", "url": reverse("tasks:open_table"),
         "container_id": open_ctx["container_id"],
         "count_builder": lambda: _tasks_qs(request.user, done=False).count(),
         "eager_render": lambda: render_table(request, open_ctx).content.decode("utf-8")},
        {"key": "done", "label": "انجام‌شده", "url": reverse("tasks:done_table"),
         "container_id": done_ctx["container_id"],
         "count_builder": lambda: _tasks_qs(request.user, done=True).count(),
         "eager_render": lambda: render_table(request, done_ctx).content.decode("utf-8")},
    ])
    return render(request, "tasks/task_list.html", {"tabs": tabs, **_form_context(None)})


@cap_required("tasks.manage")
def open_table(request):
    return render_table(request, _table_context(request, done=False))


@cap_required("tasks.manage")
def done_table(request):
    return render_table(request, _table_context(request, done=True))


@cap_required("tasks.manage")
def task_detail(request, task_id):
    task = _creator_task_or_404(request, task_id, deep=True)
    subtasks = list(task.subtasks.all())
    sub_ids = {s.pk for s in subtasks}
    rows = []
    for a in task.assignments.all():
        n = len({c.subtask_id for c in a.checks.all()} & sub_ids)
        rows.append({"a": a, "name": a.user.get_full_name() or a.user.username, "done": a.submitted_at is not None,
                     "progress": to_fa_digits(f"{n} از {len(subtasks)}") if subtasks else ""})
    all_done = bool(rows) and all(r["done"] for r in rows)
    return render(request, "tasks/task_detail.html", {
        "task": task, "subtasks": subtasks, "rows": rows, "attachments": list(task.attachments.all()),
        "overdue": bool(task.due_at and task.due_at < timezone.now() and not all_done),
    })


@cap_required("tasks.manage")
def task_edit(request, task_id):
    task = _creator_task_or_404(request, task_id, deep=True)
    return render(request, "tasks/task_edit.html", _form_context(task))


@login_required
@require_POST
def task_save(request, task_id=None):
    if not can(request.user, "tasks.manage"):
        raise Http404
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        common = dict(
            actor=request.user, title=request.POST.get("title"), description=request.POST.get("description"),
            due_at=services.build_due(request.POST.get("due_date"), request.POST.get("due_hour"),
                                      request.POST.get("due_minute")),
            subtasks=services.parse_subtasks(request.POST.get("subtasks_json")),
            assignee_ids=request.POST.getlist("assignee_ids"))
        if task_id:
            task = services.update_task(_creator_task_or_404(request, task_id), **common)
        else:
            task = services.create_task(**common)
    except ValueError as e:
        if ajax:
            return JsonResponse({"ok": False, "error": str(e)})
        messages.error(request, str(e))
        return redirect("tasks:edit", task_id) if task_id else redirect("tasks:list")
    messages.success(request, "وظیفه ویرایش شد." if task_id else "وظیفه ثبت شد.")
    if ajax:
        return JsonResponse({"ok": True, "redirect": reverse("tasks:list"),
                             "upload_url": reverse("tasks:attachment_upload", args=[task.id]),
                             "project_url": reverse("tasks:edit", args=[task.id])})
    return redirect("tasks:list")


@cap_required("tasks.manage")
@require_POST
def attachment_upload(request, task_id):
    task = _creator_task_or_404(request, task_id)
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"ok": False, "error": "فایلی ارسال نشد."}, status=400)
    try:
        att = services.add_attachment(task, uploaded=f, actor=request.user)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": att.id, "name": att.original_name})


@cap_required("tasks.manage")
@require_POST
def attachment_delete(request, attachment_id):
    att = get_object_or_404(TaskAttachment.objects.select_related("task").filter(task__created_by=request.user),
                            pk=attachment_id)
    task_id = att.task_id
    try:
        services.delete_attachment(att, request.user)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    return redirect("tasks:edit", task_id=task_id)


# ---------- تکنسین ----------
@login_required
@require_POST
def task_check(request, task_id):
    raw = (request.POST.get("subtask_id") or "").strip()
    if raw and not raw.isdigit():
        return JsonResponse({"ok": False, "error": "شناسه‌ی زیروظیفه نامعتبر است."}, status=400)
    try:
        res = services.set_check(task_id=task_id, user=request.user, subtask_id=int(raw) if raw else None,
                                 done=request.POST.get("done") in ("1", "true"))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, **res})


@login_required
@require_POST
def task_submit(request, task_id):
    try:
        services.submit_assignment(task_id=task_id, user=request.user, note=request.POST.get("note", ""))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})


def _assignment_cards(user, *, done):
    qs = (TaskAssignment.objects.filter(user=user, submitted_at__isnull=not done)
          .select_related("task__created_by").prefetch_related("task__subtasks", "task__attachments", "checks"))
    qs = qs.order_by("-submitted_at")[:50] if done else qs.order_by(F("task__due_at").asc(nulls_last=True),
                                                                    "-task__created_at")
    now, cards = timezone.now(), []
    for a in qs:
        subs = list(a.task.subtasks.all())
        checked = {c.subtask_id for c in a.checks.all()}
        cards.append({"a": a, "task": a.task, "total": len(subs),
                      "done_count": len(checked & {s.pk for s in subs}),
                      "subtasks": [{"obj": s, "checked": s.pk in checked} for s in subs],
                      "attachments": list(a.task.attachments.all()),
                      "overdue": bool(not done and a.task.due_at and a.task.due_at < now)})
    return cards


def panel_context(request, *, done):
    from projects.views import _completed_table_context, _my_tasks_table_context   # ایمپورت محلی؛ چرخه نسازد
    ctx = (_completed_table_context if done else _my_tasks_table_context)(request)
    ctx.update(cards=_assignment_cards(request.user, done=done), is_done_panel=done)
    return ctx


def eager_panel(request, *, done):
    return render_to_string("tasks/partials/my_tasks_panel.html", panel_context(request, done=done), request=request)


def _technician_only(request):
    if request.user.role != User.Role.EMPLOYEE:
        raise Http404


@login_required
def my_panel(request):
    _technician_only(request)
    return render_table(request, panel_context(request, done=False), template="tasks/partials/my_tasks_panel.html")


@login_required
def my_done_panel(request):
    _technician_only(request)
    return render_table(request, panel_context(request, done=True), template="tasks/partials/my_tasks_panel.html")
