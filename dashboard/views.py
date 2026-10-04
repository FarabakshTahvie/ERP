from django.db.models import Prefetch
from django.shortcuts import render
from django.urls import reverse

from core.capabilities import cap_required
from projects.models import Project, ProjectStage
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
