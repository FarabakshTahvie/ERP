from django.contrib import messages
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from core.capabilities import cap_required
from projects.models import Project, ProjectStage, StageKind
from projects.services import (
    ACCOUNTANT_SPECIALTY_NAME, assign_stage, cancel_project_from_stage, resume_suspended_stage,
)
from utils.generic_table import build_table_context, render_table
from utils.jalali import to_fa_digits

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
