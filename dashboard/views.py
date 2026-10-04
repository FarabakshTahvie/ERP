from django.contrib import messages
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from core.capabilities import cap_required
from notifications.models import Notification, NotificationType
from notifications.services import resend_notification
from projects.models import Project, ProjectStage, StageKind
from projects.services import (
    ACCOUNTANT_SPECIALTY_NAME, assign_stage, cancel_project_from_stage, resume_suspended_stage,
)
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits

from . import services

S = ProjectStage.Status
ACTIVE = (S.IN_PROGRESS, S.WAITING_APPROVAL, S.SUSPENDED)
STAGE_VARIANT = {S.IN_PROGRESS: "info", S.WAITING_APPROVAL: "warning", S.SUSPENDED: "error"}


def active_projects_context(request):
    stages = ProjectStage.objects.select_related("assigned_to").prefetch_related("candidate_users").order_by("order")
    qs = (Project.objects.filter(status=Project.Status.IN_PROGRESS).select_related("owner", "partner")
          .prefetch_related(Prefetch("stages", queryset=stages, to_attr="all_stages"))
          .order_by("-created_at"))

    def row_builder(p):
        sts = p.all_stages
        done = sum(1 for s in sts if s.status == S.DONE)
        percent = int(done / len(sts) * 100) if sts else 0
        cur = next((s for s in sts if s.status in ACTIVE), None)
        stage_cell, who, badge = {"type": "muted", "value": "—"}, "—", {"type": "muted", "value": "—"}
        if cur:
            candidates = len(cur.candidate_users.all())
            variant = STAGE_VARIANT[cur.status]
            if cur.assigned_to_id:
                who = cur.assigned_to.get_full_name() or cur.assigned_to.username
            elif candidates:
                who = to_fa_digits(f"در استخر ({candidates} نفر)")
            else:
                who = "نیازمند تعیین مسئول"
                if cur.status == S.IN_PROGRESS:
                    variant = "warning"
            stage_cell = {"type": "text", "value": cur.title}
            badge = {"type": "badge", "value": cur.get_status_display(), "variant": variant}
        return {"url": reverse("projects:staff_project_overview", args=[p.id]), "cells": [
            {"type": "text", "value": p.name},
            {"type": "muted", "value": to_fa_digits(p.code)},
            stage_cell,
            {"type": "muted", "value": who},
            {"type": "muted", "value": to_fa_digits(f"{percent}٪")},
            badge,
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "پروژه", "sort_field": "name"},
            {"label": "کد", "sort_field": "code"},
            {"label": "مرحله‌ی فعلی"},
            {"label": "مسئول"},
            {"label": "پیشرفت"},
            {"label": "وضعیت مرحله"},
        ],
        row_builder=row_builder, container_id="table-manager-projects", param_prefix="dm_",
        empty_icon="folder-kanban", empty_text="پروژه‌ی در حال اجرایی نیست.",
        list_url=reverse("dashboard:projects_table"),
        search_fields=["name", "code", "owner__name", "partner__name"],
        search_placeholder="جستجو در نام پروژه، کد یا طرف‌حساب...",
    )


def overview_view(request):
    """هم از /manager/ صدا زده می‌شود هم از home_view برای مدیر. محافظت با فراخوان است."""
    ctx = services.dashboard_context()
    ctx.update(active_projects_context(request))
    return render(request, "dashboard/overview.html", ctx)


@cap_required("dashboard.manager")
def overview(request):
    return overview_view(request)


@cap_required("dashboard.manager")
def projects_table(request):
    return render_table(request, active_projects_context(request))


def stages_table_context(request):
    now = timezone.now()

    def row_builder(s):
        if s.assigned_to_id:
            who = s.assigned_to.get_full_name() or s.assigned_to.username
        elif s.has_pool:
            who = to_fa_digits(f"در استخر ({len(s.candidate_users.all())} نفر)")
        else:
            who = "بدون مسئول"
        return {"url": reverse("dashboard:assign_stage", args=[s.id]), "cells": [
            {"type": "text", "value": s.project.name},
            {"type": "text", "value": s.title},
            {"type": "badge", "value": who, "variant": "warning" if s.no_owner else "neutral"},
            {"type": "muted", "value": to_fa_digits(f"{services._since(s.last_move, now)} روز پیش")},
        ]}

    return build_table_context(
        request, services.active_stages_qs(),
        columns=[
            {"label": "پروژه", "sort_field": "project__name"},
            {"label": "مرحله", "sort_field": "title"},
            {"label": "مسئول", "sort_field": "no_owner", "filter_key": "no_owner", "filter_type": "boolean",
             "filter_field": "no_owner", "true_label": "بدون مسئول", "false_label": "دارای مسئول یا استخر"},
            {"label": "آخرین حرکت", "sort_field": "last_move"},
        ],
        row_builder=row_builder, container_id="table-manager-stages", param_prefix="ds_",
        empty_icon="check-circle", empty_text="مرحله‌ی در حال انجامی نیست.",
        list_url=reverse("dashboard:stages_table"),
        search_fields=["project__name", "title", "assigned_to__first_name", "assigned_to__last_name",
                       "assigned_to__username"],
        search_placeholder="جستجو در پروژه، مرحله یا مسئول...",
    )


@cap_required("stages.assign")
def stages_page(request):
    return render(request, "dashboard/stages.html", stages_table_context(request))


@cap_required("stages.assign")
def stages_table(request):
    return render_table(request, stages_table_context(request))


@cap_required("stages.assign")
def assign_stage_page(request, stage_id):
    stage = get_object_or_404(
        ProjectStage.objects.select_related("project", "step_template__responsible_specialty", "assigned_to"),
        pk=stage_id)
    if request.method == "POST":
        raw = (request.POST.get("target_user") or "").strip()
        target = User.objects.filter(pk=int(raw)).first() if raw.isdigit() else None
        try:
            assign_stage(stage, target_user=target, actor=request.user, comment=request.POST.get("comment"))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("dashboard:assign_stage", stage.id)
        messages.success(request, f"مرحله «{stage.title}» به {target.get_full_name() or target.username} ارجاع شد.")
        return redirect("dashboard:stages")

    spec = stage.step_template.responsible_specialty
    employees = (User.objects.filter(role=User.Role.EMPLOYEE, is_active=True)
                 .prefetch_related("specialties").order_by("first_name", "last_name", "username"))
    accountant_only = stage.kind in (StageKind.PROFORMA, StageKind.FINAL_REVIEW)
    if accountant_only:
        employees = employees.filter(specialties__name=ACCOUNTANT_SPECIALTY_NAME)
    same, others = [], []
    for u in employees:
        is_same = bool(spec and any(s.id == spec.id for s in u.specialties.all()))
        (same if is_same else others).append(u)
    return render(request, "dashboard/assign_stage.html", {
        "stage": stage, "specialty": spec, "same": same, "others": others,
        "accountant_only": accountant_only,
        "can_assign": (stage.status == ProjectStage.Status.IN_PROGRESS
                       and stage.project.status == Project.Status.IN_PROGRESS),
        "events": stage.events.select_related("actor").order_by("-created_at")[:5],
    })


@cap_required("stages.assign")
def suspended_page(request):
    return render(request, "dashboard/suspended.html", {"items": services.suspended_items()})


@cap_required("stages.assign")
@require_POST
def suspended_resume(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    try:
        resume_suspended_stage(stage, actor=request.user, comment=request.POST.get("comment"))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"مرحله «{stage.title}» به چرخه برگشت.")
    return redirect("dashboard:suspended")


@cap_required("projects.cancel")
@require_POST
def suspended_cancel(request, stage_id):
    stage = get_object_or_404(ProjectStage.objects.select_related("project"), pk=stage_id)
    try:
        cancel_project_from_stage(stage, actor=request.user, comment=request.POST.get("comment"),
                                  cancel_invoice=request.POST.get("cancel_invoice") == "on")
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"پروژه «{stage.project.name}» لغو شد.")
    return redirect("dashboard:suspended")


def notifications_context(request):
    qs = (Notification.objects.select_related("user")
          .annotate(n_clicks=Count("click_events")).order_by("-created_at"))
    variant = {"pending": "warning", "push_sent": "info", "seen": "success", "sms_sent": "info", "failed": "error"}

    def row_builder(n):
        return {"url": reverse("dashboard:notification_detail", args=[n.id]), "cells": [
            {"type": "text", "value": n.get_notification_type_display()},
            {"type": "text", "value": n.user.get_full_name() or n.user.username},
            {"type": "badge", "value": n.get_status_display(), "variant": variant.get(n.status, "neutral")},
            {"type": "muted", "value": jalali_str(n.created_at, fmt="%Y/%m/%d %H:%M")},
            {"type": "muted", "value": jalali_str(n.seen_at, fmt="%Y/%m/%d %H:%M") if n.seen_at else "دیده نشده"},
            {"type": "muted", "value": to_fa_digits(n.n_clicks)},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "نوع", "sort_field": "notification_type", "filter_key": "type", "filter_type": "select",
             "filter_field": "notification_type", "choices": NotificationType.choices},
            {"label": "گیرنده", "sort_field": "user__last_name"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": Notification.Status.choices},
            {"label": "زمان", "sort_field": "created_at"},
            {"label": "دیده‌شدن", "sort_field": "seen_at"},
            {"label": "کلیک", "sort_field": "n_clicks"},
        ],
        row_builder=row_builder, container_id="table-manager-notifications", param_prefix="nt_",
        empty_icon="bell", empty_text="اطلاع‌رسانی‌ای ثبت نشده.",
        list_url=reverse("dashboard:notifications_table"),
        search_fields=["title", "user__first_name", "user__last_name", "user__username"],
        search_placeholder="جستجو در عنوان یا گیرنده...",
    )


@cap_required("notifications.manage")
def notifications_page(request):
    return render(request, "dashboard/notifications.html", notifications_context(request))


@cap_required("notifications.manage")
def notifications_table(request):
    return render_table(request, notifications_context(request))


@cap_required("notifications.manage")
def notification_detail(request, notification_id):
    n = get_object_or_404(Notification.objects.select_related("user"), pk=notification_id)
    return render(request, "dashboard/notification_detail.html", {
        "n": n, "clicks": n.click_events.order_by("-clicked_at")[:20],
        "can_resend": n.status == Notification.Status.FAILED and n.notification_type != NotificationType.INVOICE_ISSUED,
    })


@cap_required("notifications.manage")
@require_POST
def notification_resend(request, notification_id):
    n = get_object_or_404(Notification, pk=notification_id)
    try:
        n = resend_notification(n, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"وضعیت بعد از ارسال دوباره: {n.get_status_display()}")
    return redirect("dashboard:notification_detail", n.id)
