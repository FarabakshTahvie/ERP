from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Max, Case, When, BooleanField

from core.capabilities import cap_required, can
from accounts.models import User
from utils.jalali import to_fa_digits, jalali_str
from utils.generic_table import build_table_context, render_table
from .models import Task, TaskAssignment, TaskAttachment
from . import services


@cap_required("tasks.manage")
def task_list(request):
    """
    فهرست وظایف مدیر/حسابدار با دو تب: وظایف (در جریان) و انجام‌شده.
    """
    return render(request, "tasks/task_list.html", {
        "active_tab": request.GET.get("tab", "open"),
        "technicians": User.objects.filter(is_active=True, role=User.Role.EMPLOYEE).order_by("last_name", "first_name"),
    })


def _build_task_table_context(request, status_filter):
    now = timezone.now()
    tasks_all = Task.objects.filter(created_by=request.user).annotate(
        n_total=Count("assignments", distinct=True),
        n_done=Count("assignments", filter=Q(assignments__submitted_at__isnull=False), distinct=True),
        finished_at=Max("assignments__submitted_at")
    )
    
    # Filter by open vs done
    task_ids = []
    for t in tasks_all:
        done = (t.n_total > 0 and t.n_done == t.n_total)
        if status_filter == "done" and done:
            task_ids.append(t.id)
        elif status_filter == "open" and not done:
            task_ids.append(t.id)

    qs = Task.objects.filter(pk__in=task_ids).annotate(
        n_total=Count("assignments", distinct=True),
        n_done=Count("assignments", filter=Q(assignments__submitted_at__isnull=False), distinct=True),
        finished_at=Max("assignments__submitted_at")
    ).prefetch_related("assignments__user").order_by("-created_at")

    def row_builder(t):
        assignees_names = [a.user.get_full_name() or a.user.username for a in t.assignments.all()]
        if len(assignees_names) <= 3:
            assignees_str = "، ".join(assignees_names)
        else:
            assignees_str = "، ".join(assignees_names[:3]) + f" و {len(assignees_names)-3} نفر دیگر"

        progress_str = f"{t.n_done} از {t.n_total} نفر"

        if status_filter == "done":
            date_str = jalali_str(t.finished_at, fmt="%Y/%m/%d %H:%M") if t.finished_at else "-"
            cells = [
                {"type": "text", "value": t.title},
                {"type": "text", "value": assignees_str},
                {"type": "text", "value": progress_str},
                {"type": "text", "value": date_str},
            ]
        else:
            is_overdue = t.due_at and t.due_at < now
            status_val = "ددلاین گذشته" if is_overdue else "در جریان"
            status_var = "error" if is_overdue else "info"
            due_str = jalali_str(t.due_at, fmt="%Y/%m/%d %H:%M") if t.due_at else "بدون سررسید"

            cells = [
                {"type": "text", "value": t.title},
                {"type": "text", "value": due_str},
                {"type": "text", "value": assignees_str},
                {"type": "text", "value": progress_str},
                {"type": "badge", "value": status_val, "variant": status_var},
            ]

        return {
            "url": reverse("tasks:detail", args=[t.id]),
            "cells": cells,
        }

    cols = [
        {"label": "عنوان", "sort_field": "title"},
        {"label": "سررسید", "sort_field": "due_at"} if status_filter == "open" else {"label": "عنوان"},
        {"label": "مسئولان"},
        {"label": "پیشرفت"},
        {"label": "وضعیت"} if status_filter == "open" else {"label": "تاریخ ثبت نهایی"},
    ]
    if status_filter == "done":
        cols = [
            {"label": "عنوان", "sort_field": "title"},
            {"label": "مسئولان"},
            {"label": "پیشرفت"},
            {"label": "تاریخ ثبت نهایی"},
        ]

    prefix = "tko_" if status_filter == "open" else "tkd_"
    container_id = "table-tasks-open" if status_filter == "open" else "table-tasks-done"
    list_url = reverse("tasks:open_table" if status_filter == "open" else "tasks:done_table")

    return build_table_context(
        request, qs,
        columns=cols,
        row_builder=row_builder,
        container_id=container_id,
        param_prefix=prefix,
        empty_icon="check-square",
        empty_text="وظیفه‌ای یافت نشد.",
        list_url=list_url,
        search_fields=["title", "description", "assignments__user__first_name", "assignments__user__last_name", "assignments__user__username"],
        search_placeholder="جستجو در عنوان یا نام مسئول...",
    )


@cap_required("tasks.manage")
def open_table(request):
    return render_table(request, _build_task_table_context(request, "open"))


@cap_required("tasks.manage")
def done_table(request):
    return render_table(request, _build_task_table_context(request, "done"))


@login_required
@require_POST
def task_save(request, task_id=None):
    if not can(request.user, "tasks.manage"):
        raise Http404
    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    try:
        kw = dict(
            actor=request.user,
            title=request.POST.get("title"),
            description=request.POST.get("description"),
            due_at=services.build_due(request.POST.get("due_date"), request.POST.get("due_hour"), request.POST.get("due_minute")),
            subtasks=services.parse_subtasks(request.POST.get("subtasks_json")),
            assignee_ids=request.POST.getlist("assignee_ids")
        )
        task = (services.update_task(get_object_or_404(Task, pk=task_id), **kw) if task_id
                else services.create_task(**{**kw, "subtasks": kw["subtasks"] or []}))
    except ValueError as e:
        if ajax:
            return JsonResponse({"ok": False, "error": str(e)})
        messages.error(request, str(e))
        return redirect("tasks:list")
    
    messages.success(request, "وظیفه ثبت شد.")
    if ajax:
        return JsonResponse({
            "ok": True,
            "redirect": reverse("tasks:list"),
            "upload_url": reverse("tasks:attachment_upload", args=[task.id]),
            "project_url": reverse("tasks:edit", args=[task.id]),
        })
    return redirect("tasks:list")


@cap_required("tasks.manage")
def task_detail(request, task_id):
    task = get_object_or_404(Task.objects.select_related("created_by").prefetch_related("subtasks", "assignments__user", "assignments__checks", "attachments"), pk=task_id)
    if task.created_by_id != request.user.id and not request.user.is_superuser:
        raise Http404
    return render(request, "tasks/task_detail.html", {"task": task})


@cap_required("tasks.manage")
def task_edit(request, task_id):
    task = get_object_or_404(Task.objects.select_related("created_by").prefetch_related("subtasks", "assignments__user", "attachments"), pk=task_id)
    if task.created_by_id != request.user.id and not request.user.is_superuser:
        raise Http404
    technicians = User.objects.filter(is_active=True, role=User.Role.EMPLOYEE).order_by("last_name", "first_name")
    return render(request, "tasks/task_edit.html", {"task": task, "technicians": technicians})


@cap_required("tasks.manage")
@require_POST
def attachment_upload(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    if task.created_by_id != request.user.id:
        return JsonResponse({"ok": False, "error": "دسترسی غیرمجاز"}, status=403)
    file_obj = request.FILES.get("file")
    if not file_obj:
        return JsonResponse({"ok": False, "error": "فایلی ارسال نشد."}, status=400)
    try:
        att = services.add_attachment(task, uploaded=file_obj, actor=request.user)
        return JsonResponse({
            "ok": True,
            "id": att.id,
            "name": att.original_name,
            "url": att.file.url,
            "is_image": att.is_image,
        })
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


@cap_required("tasks.manage")
@require_POST
def attachment_delete(request, attachment_id):
    att = get_object_or_404(TaskAttachment.objects.select_related("task"), pk=attachment_id)
    try:
        services.delete_attachment(att, request.user)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
    except ValueError as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return redirect("tasks:edit", task_id=att.task_id)


@login_required
@require_POST
def task_check(request, task_id):
    subtask_id = request.POST.get("subtask_id")
    if subtask_id == "" or subtask_id is None:
        st_id = None
    else:
        try:
            st_id = int(subtask_id)
        except ValueError:
            return JsonResponse({"ok": False, "error": "شناسه زیروظیفه نامعتبر است."}, status=400)
    
    done = request.POST.get("done") == "true" or request.POST.get("done") == "1"
    try:
        res = services.set_check(task_id=task_id, user=request.user, subtask_id=st_id, done=done)
        return JsonResponse({"ok": True, **res})
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)


@login_required
@require_POST
def task_submit(request, task_id):
    note = request.POST.get("note", "")
    try:
        services.submit_assignment(task_id=task_id, user=request.user, note=note)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": True})
        messages.success(request, "وظیفه با موفقیت ثبت شد.")
    except ValueError as e:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": str(e)}, status=400)
        messages.error(request, str(e))
    return redirect("/")


@login_required
def my_panel(request):
    """
    پنل کارهای من (تکنسین) - وظایف در جریان.
    """
    assignments = TaskAssignment.objects.filter(user=request.user, submitted_at__isnull=True).select_related("task__created_by").prefetch_related("task__subtasks", "task__assignments", "checks", "task__attachments")
    return render(request, "tasks/partials/my_tasks_panel.html", {"task_assignments": assignments, "is_done_panel": False})


@login_required
def my_done_panel(request):
    """
    پنل کارهای من (تکنسین) - وظایف انجام‌شده (حداکثر ۵۰).
    """
    assignments = TaskAssignment.objects.filter(user=request.user, submitted_at__isnull=False).select_related("task__created_by").prefetch_related("task__subtasks", "task__assignments", "checks", "task__attachments").order_by("-submitted_at")[:50]
    return render(request, "tasks/partials/my_tasks_panel.html", {"task_assignments": assignments, "is_done_panel": True})
