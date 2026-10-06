from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import json
from decimal import Decimal, InvalidOperation
from django.template.loader import render_to_string
from utils.generic_table import build_table_context, render_table
from utils.tabs import build_tabs_context
from django.core.exceptions import ValidationError
from django.db.models import Sum, Prefetch, F, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from utils.utils import separate_digits
from utils.jalali_forms import JalaliDateField
from utils.jalali import jalali_str, to_fa_digits
from accounts.models import User
from core.models import Party
from catalog.models import Service, Item
from catalog.services import has_global_margin, resolve_margin_percents
from .models import Project, ProjectStage, StageApproval, StageKind, ProjectFile
from .stage_ops import can_upload_to_stage, add_stage_file, upload_requirement, complete_stage, cut_files, cuts_summary, set_cut
from .services import (
    approval_design_files,
    claim_stage, advance_stage, transfer_stage, get_transfer_candidates,
    create_project_from_technician_intake, user_can_create_projects,
    decide_stage_approval, can_edit_project, can_edit_pricing, project_prices_editable,
    update_project_from_technician_edit, EDITABLE_PROJECT_STATUSES,
    stage_approval_action, can_search_parties_for_purchase, NOT_SENT,
    update_visit_date, user_is_accountant, user_can_access_accounting,
)
from .proforma import (
    parse_service_rows, parse_extra_rows, save_proforma, issue_proforma, proforma_stage, can_issue_proforma
)
from finance.services import create_customer_payment
from inventory.services import user_can_manage_inventory, low_stock_items_count


def _cost_values(project):
    def money(v):
        return str(int(v)) if v else ""
    return {
        "installation_fee": money(project.installation_fee),
        "shipping_fee": money(project.shipping_fee),
        "extra_fee": money(project.extra_fee),
        "contract_date": jalali_str(project.contract_date, fmt="%Y/%m/%d") if project.contract_date else "",
        "notes": project.notes or "",
    }



def _parse_json_lines_strict(raw_value):
    """برای ویرایش: None یعنی «ارسال نشده». JSON خراب خطا می‌دهد، نه لیست خالی (که ردیف‌ها را پاک می‌کرد)."""
    if raw_value is None:
        return None
    try:
        data = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("اطلاعات ردیف‌ها نامعتبر است؛ صفحه را دوباره باز کنید.")
    if not isinstance(data, list):
        raise ValueError("اطلاعات ردیف‌ها نامعتبر است؛ صفحه را دوباره باز کنید.")
    return data


def _line_choices(project):
    """خدمات/کالاهای قابل انتخاب + موارد فعلی پروژه (حتی اگر بعداً غیرفعال شده باشند)."""
    services = list(Service.objects.filter(is_active=True).exclude(children__isnull=False))
    used = set(project.services.values_list("service_id", flat=True)) - {s.id for s in services}
    if used:
        services += list(Service.objects.filter(pk__in=used))
    items = list(Item.objects.filter(is_active=True))
    used = set(project.extra_materials.values_list("item_id", flat=True)) - {i.id for i in items}
    if used:
        items += list(Item.objects.filter(pk__in=used))
    return services, items



DURATION_HINTS = {
    range(0, 5): "معمولاً چند ساعت طول می‌کشد.",
    range(5, 17): "معمولاً یک روز کاری طول می‌کشد.",
    range(17, 49): "معمولاً دو تا سه روز کاری طول می‌کشد.",
}


def _is_technician(user):
    return user.is_authenticated and user.role == User.Role.EMPLOYEE


def _duration_hint(hours):
    if not hours:
        return ""
    for r, text in DURATION_HINTS.items():
        if hours in r:
            return text
    return "ممکن است چند روز طول بکشد."


def _my_tasks_base_qs(request):
    return (ProjectStage.objects
            .filter(status=ProjectStage.Status.IN_PROGRESS, assigned_to=request.user)
            .exclude(project__status=Project.Status.CANCELLED)
            .select_related("project", "step_template").order_by("project__name", "order"))


def _my_tasks_table_context(request):
    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]),
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "badge", "value": "در حال انجام", "variant": "info"},
            ],
        }

    return build_table_context(
        request, _my_tasks_base_qs(request),
        columns=[
            {"label": "پروژه", "sort_field": "project__name"},
            {"label": "مرحله", "sort_field": "title"},
            {"label": "وضعیت"},
        ],
        row_builder=row_builder,
        container_id="table-my-tasks",
        param_prefix="mt_",
        empty_icon="check-circle", empty_text="فعلاً کار فعالی برای شما ثبت نشده.",
        list_url=reverse("projects:dashboard_my_tasks_table"),
        search_fields=["project__name", "title", "client_label"],
    )


@login_required
@user_passes_test(_is_technician)
def dashboard_my_tasks_table(request):
    from tasks.models import TaskAssignment
    ctx = _my_tasks_table_context(request)
    ctx["task_assignments"] = TaskAssignment.objects.filter(user=request.user, submitted_at__isnull=True).select_related("task__created_by").prefetch_related("task__subtasks", "task__assignments", "checks", "task__attachments")
    ctx["is_done_panel"] = False
    return render_table(request, ctx, template="tasks/partials/my_tasks_panel.html")


def _claimable_base_qs(request):
    return (ProjectStage.objects
            .filter(status=ProjectStage.Status.IN_PROGRESS, candidate_users=request.user)
            .exclude(assigned_to=request.user)
            .exclude(project__status=Project.Status.CANCELLED)
            .select_related("project", "step_template").distinct().order_by("project__name", "order"))


def _claimable_table_context(request):
    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]),
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "badge", "value": "بدون مسئول ثابت", "variant": "warning"},
            ],
        }

    return build_table_context(
        request, _claimable_base_qs(request),
        columns=[
            {"label": "پروژه", "sort_field": "project__name"},
            {"label": "مرحله", "sort_field": "title"},
            {"label": "وضعیت"},
        ],
        row_builder=row_builder,
        container_id="table-claimable",
        param_prefix="cl_",
        empty_icon="folder-kanban", empty_text="فعلاً کاری در استخر قابل‌برداشتن نیست.",
        list_url=reverse("projects:dashboard_claimable_table"),
        search_fields=["project__name", "title", "client_label"],
    )


@login_required
@user_passes_test(_is_technician)
def dashboard_claimable_table(request):
    return render_table(request, _claimable_table_context(request))


def _completed_base_qs(request):
    return ProjectStage.objects.filter(
        status=ProjectStage.Status.DONE, completed_by=request.user
    ).select_related("project", "step_template").order_by("-completed_at")


def _completed_table_context(request):
    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]) if stage.assigned_to_id == request.user.id else None,
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "muted", "value": jalali_str(stage.completed_at, fmt="%Y/%m/%d %H:%M")},
                {"type": "badge", "value": "تکمیل شد", "variant": "success"},
            ],
        }

    return build_table_context(
        request, _completed_base_qs(request),
        columns=[
            {"label": "پروژه", "sort_field": "project__name"},
            {"label": "مرحله", "sort_field": "title"},
            {"label": "تاریخ تکمیل", "sort_field": "completed_at"},
            {"label": "وضعیت"},
        ],
        row_builder=row_builder,
        container_id="table-completed",
        param_prefix="dn_",
        empty_icon="check-circle", empty_text="هنوز هیچ کاری را تکمیل نکرده‌اید.",
        list_url=reverse("projects:dashboard_completed_table"),
        search_fields=["project__name", "title"],
    )


@login_required
@user_passes_test(_is_technician)
def dashboard_completed_table(request):
    from tasks.models import TaskAssignment
    ctx = _completed_table_context(request)
    ctx["task_assignments"] = TaskAssignment.objects.filter(user=request.user, submitted_at__isnull=False).select_related("task__created_by").prefetch_related("task__subtasks", "task__assignments", "checks", "task__attachments").order_by("-submitted_at")[:50]
    ctx["is_done_panel"] = True
    return render_table(request, ctx, template="tasks/partials/my_tasks_panel.html")


def _my_projects_base_qs(request):
    return Project.objects.filter(created_by=request.user).order_by("-created_at")


def _my_projects_table_context(request):
    def row_builder(project):
        total = project.stages.count()
        done = project.stages.filter(status=ProjectStage.Status.DONE).count()
        percent = int((done / total) * 100) if total else 0
        status_variant = {"completed": "success", "cancelled": "error", "in_progress": "info"}.get(project.status, "neutral")
        return {
            "url": reverse("projects:staff_project_overview", args=[project.id]),
            "cells": [
                {"type": "text", "value": project.name},
                {"type": "muted", "value": to_fa_digits(project.code)},
                {"type": "muted", "value": to_fa_digits(f"{percent}٪")},
                {"type": "badge", "value": project.get_status_display(), "variant": status_variant},
            ],
        }

    return build_table_context(
        request, _my_projects_base_qs(request),
        columns=[
            {"label": "پروژه", "sort_field": "name"},
            {"label": "کد", "sort_field": "code"},
            {"label": "پیشرفت"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": Project.Status.choices},
        ],
        row_builder=row_builder,
        container_id="table-my-projects",
        param_prefix="pr_",
        empty_icon="folder-kanban", empty_text="هنوز پروژه‌ای ثبت نکرده‌اید.",
        list_url=reverse("projects:dashboard_my_projects_table"),
        search_fields=["name", "code"],
    )


@login_required
@user_passes_test(user_can_create_projects)
def dashboard_my_projects_table(request):
    return render_table(request, _my_projects_table_context(request))


# Remove _can_view_financial_stats, _financial_stats_summary, _financial_ledger_table_context, dashboard_financial_ledger_table


def technician_home_view(request, user):
    can_create = user_can_create_projects(user)
    can_manage_inventory = user_can_manage_inventory(user)
    can_review = user_can_access_accounting(user)

    from finance.models import Payment
    pending_payments_count = 0
    if can_review:
        pending_qs = Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY)
        pending_payments_count = pending_qs.count()

    low_stock_count = low_stock_items_count() if can_manage_inventory else 0

    def _eager(context_builder):
        return lambda: render_to_string(
            "utils/partials/generic_table.html", context_builder(request), request=request,
        )

    tabs = [
        {
            "key": "my_tasks", "label": "کارهای من",
            "count_builder": lambda: _my_tasks_base_qs(request).count(),
            "url": reverse("projects:dashboard_my_tasks_table"),
            "container_id": "tab-panel-mytasks",
            "eager_render": _eager(_my_tasks_table_context),
        },
        {
            "key": "claimable", "label": "قابل برداشتن",
            "count_builder": lambda: _claimable_base_qs(request).count(),
            "url": reverse("projects:dashboard_claimable_table"),
            "container_id": "tab-panel-claimable",
            "eager_render": _eager(_claimable_table_context),
        },
        {
            "key": "completed", "label": "انجام‌شده",
            "count_builder": lambda: _completed_base_qs(request).count(),
            "url": reverse("projects:dashboard_completed_table"),
            "container_id": "tab-panel-completed",
            "eager_render": _eager(_completed_table_context),
        },
    ]
    if can_create:
        tabs.append({
            "key": "my_projects", "label": "پروژه‌های من",
            "count_builder": lambda: _my_projects_base_qs(request).count(),
            "url": reverse("projects:dashboard_my_projects_table"),
            "container_id": "tab-panel-myprojects",
            "eager_render": _eager(_my_projects_table_context),
        })
    if can_manage_inventory:
        from inventory.views import _stock_table_context
        tabs.append({
            "key": "stock", "label": "موجودی انبار",
            "hint": "جمع موجودی در همه‌ی انبارها نشان داده می‌شود (فعلاً فقط «انبار مرکزی»).",
            "url": reverse("inventory:stock_table"),
            "container_id": "tab-panel-stock-table",
            "eager_render": _eager(_stock_table_context),
        })
        from .views_ops import part_requests_table_context
        from .models import PartRequest
        tabs.append({
            "key": "part_requests", "label": "درخواست قطعه",
            "count_builder": lambda: PartRequest.objects.filter(status=PartRequest.Status.REQUESTED).count(),
            "url": reverse("projects:part_requests_table"), "container_id": "tab-panel-part-requests",
            "eager_render": _eager(part_requests_table_context),
        })

    tabs_context = build_tabs_context(request, tabs)

    return render(request, "projects/technician_home.html", {
        "can_create_projects": can_create,
        "can_review_payments": can_review,
        "can_manage_inventory": can_manage_inventory,
        "pending_payments_count": pending_payments_count,
        "low_stock_count": low_stock_count,
        "tabs": tabs_context,
    })


def _render_staff_project_view(request, project, highlight_stage_id=None):
    """
    یک صفحه‌ی واحد برای «مشاهده‌ی پروژه»: هم تکنسینِ ثبت‌کننده/مسئولان پروژه، هم تکنسین‌هایی
    که یک مرحله را برداشته‌اند یا کاندیدای آن هستند، از همین تابع/تمپلیت استفاده می‌کنند تا
    اطلاعات نمایش‌داده‌شده (اطلاعات تماس، آدرس، فایل‌ها، روند کامل مراحل) یکسان باشد؛ فقط
    دکمه‌های اکشن (برداشتن/تکمیل/انتقال) بسته به اینکه کاربر برای کدام مرحله مسئول یا
    کاندیدا است، نمایش داده می‌شوند.
    """
    user = request.user
    is_project_level_viewer = (
        user.is_superuser or user.role == User.Role.ADMIN
        or project.created_by_id == user.id
        or project.assigned_technicians.filter(pk=user.id).exists()
        or project.participants.filter(user=user).exists()
        or user_is_accountant(user)
    )

    stages = list(
        project.stages.select_related("assigned_to", "step_template")
        .prefetch_related("events__actor", "candidate_users",
                          Prefetch("files", queryset=ProjectFile.objects.select_related("uploaded_by").order_by("created_at", "pk"), to_attr="file_list"))
        .order_by("order")
    )

    from . import ops
    my_stage_ids = set()
    for s in stages:
        s.ops = ops.ops_context(user, s)
        candidate_ids = {u.id for u in s.candidate_users.all()}
        s.is_mine = s.assigned_to_id == user.id
        s.is_candidate = user.id in candidate_ids
        s.candidate_count = len(candidate_ids)
        if s.is_mine or s.is_candidate:
            my_stage_ids.add(s.id)
        s.transfer_candidates = get_transfer_candidates(s) if s.is_mine else None
        s.can_upload = s.status == ProjectStage.Status.IN_PROGRESS and can_upload_to_stage(user, s)
        s.upload_req = upload_requirement(s)
        s.file_upload_url = reverse("projects:stage_file_upload", args=[s.id])
        s.is_gcode = s.kind == StageKind.GCODE
        s.anchor = f"stage-{s.id}"

    cut_rows = []
    if any(s.kind == StageKind.CUTTING for s in stages):
        for f in cut_files(project):
            done = {c.index for c in f.cuts_done.all() if 1 <= c.index <= f.cut_count}
            cut_rows.append({"file": f, "done_count": len(done),
                             "cells": [{"n": i, "done": i in done} for i in range(1, f.cut_count + 1)]})

    if not is_project_level_viewer and not my_stage_ids:
        raise Http404

    ops_items = []
    if any(getattr(s, "ops", None) and s.ops.get("can_edit") for s in stages):
        ops_items = [{"id": i.id, "name": i.name, "unit": i.get_unit_display()} for i in Item.objects.filter(is_active=True)]

    from . import stage_move
    can_move = stage_move.can_move_stages(user, project)
    move_current, move_options = stage_move.move_options(project) if can_move else (None, [])

    titles = {s.id: s.title for s in stages}
    parked_ids = {s.return_to_id for s in stages if s.return_to_id}
    for s in stages:
        s.parked = s.id in parked_ids
        s.return_title = titles.get(s.return_to_id)

    return render(request, "projects/staff_project_overview.html", {
        "project": project, "stages": stages, "highlight_stage_id": highlight_stage_id,
        "can_edit": can_edit_project(user, project) and project.status in EDITABLE_PROJECT_STATUSES,
        "can_price": can_edit_pricing(user, project) and project.status in EDITABLE_PROJECT_STATUSES,
        "cut_rows": cut_rows,
        "can_final_review": ops.can_view_final_review(user, project) and any(s.kind == StageKind.FINAL_REVIEW for s in stages),
        "ops_items": ops_items,
        "can_move": can_move,
        "move_current": move_current,
        "move_options": move_options,
    })


@login_required
def staff_project_overview(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    return _render_staff_project_view(request, project)


@login_required
def portal_stage_approval(request, approval_id):
    from finance.services import create_customer_payment
    from core.capabilities import can

    approval = get_object_or_404(
        StageApproval.objects.select_related("stage__project", "stage__step_template", "sent_to_party"),
        pk=approval_id,
    )
    party = getattr(request.user, "party", None)
    is_owner = bool(party and party.id == approval.sent_to_party_id)
    if not is_owner and not can(request.user, "accounting.access"):
        raise Http404

    stage = approval.stage
    invoice = getattr(stage.project, "invoice", None)
    needs_payment = stage.step_template.requires_payment_selection

    def render_page(**extra):
        ctx = {"approval": approval, "stage": stage, "invoice": invoice,
               "needs_payment": needs_payment, "readonly": not is_owner,
               "design_files": approval_design_files(stage)}
        ctx.update(extra)
        return render(request, "projects/portal_stage_approval.html", ctx)

    def finish():
        return redirect("finance:portal_invoice_detail", invoice.uuid) if invoice else redirect("home")

    if approval.decision != StageApproval.Decision.PENDING:
        return render_page(already_decided=True)

    if request.method == "POST":
        if not is_owner:
            raise Http404
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        if action == "reject":
            if not comment:
                messages.error(request, "برای رد، ذکر دلیل اجباری است.")
                return render_page()
            with transaction.atomic():
                locked = StageApproval.objects.select_for_update().get(pk=approval.pk)
                if locked.decision != StageApproval.Decision.PENDING:
                    messages.info(request, "این درخواست قبلاً بررسی شده است.")
                    return finish()
                decide_stage_approval(locked, actor=request.user, decision=StageApproval.Decision.REJECTED, comment=comment)
            messages.success(request, "پاسخ شما ثبت شد.")
            return finish()

        if action == "approve":
            if needs_payment and invoice and request.POST.get("seen_total") != str(int(invoice.total_amount)):
                messages.warning(request, "مبلغ فاکتور از زمان باز شدن این صفحه تغییر کرده است. مبلغ جدید را بررسی کنید و دوباره تایید بزنید.")
                return redirect("projects:portal_stage_approval", approval.id)
            try:
                with transaction.atomic():
                    locked = StageApproval.objects.select_for_update().get(pk=approval.pk)
                    if locked.decision != StageApproval.Decision.PENDING:
                        messages.info(request, "این درخواست قبلاً بررسی شده است.")
                        return finish()
                    if needs_payment and invoice:
                        create_customer_payment(
                            invoice=invoice,
                            method=request.POST.get("payment_method"),
                            amount_raw=request.POST.get("payment_amount"),
                            reference_number=request.POST.get("reference_number", ""),
                            note=comment,
                            receipt_file=request.FILES.get("receipt_file"),
                            cheque_number=request.POST.get("cheque_number", ""),
                            cheque_bank=request.POST.get("cheque_bank", ""),
                        )
                    decide_stage_approval(
                        locked, actor=request.user, decision=StageApproval.Decision.APPROVED,
                        comment=comment or "تایید شد توسط طرف‌حساب",
                    )
            except ValueError as e:
                messages.error(request, str(e))
                return render_page()
            messages.success(request, "تایید شما با موفقیت ثبت شد.")
            return finish()

    return render_page()


@login_required
def portal_stage_file(request, approval_id, file_id):
    from core.capabilities import can
    approval = get_object_or_404(StageApproval.objects.select_related("stage__project"), pk=approval_id)
    party = getattr(request.user, "party", None)
    is_owner = bool(party and party.id == approval.sent_to_party_id)
    if not is_owner and not can(request.user, "accounting.access"):
        raise Http404
    f = next((x for x in approval_design_files(approval.stage) if x.pk == file_id), None)
    if f is None:
        raise Http404
    inline = f.kind in ("pdf", "image")
    response = FileResponse(f.file.open("rb"), as_attachment=not inline, filename=f.display_name)
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def project_progress(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    party = getattr(request.user, "party", None)
    if not party or party.id not in (project.partner_id, project.owner_id):
        raise Http404

    invoice = getattr(project, "invoice", None)
    stages = []
    for s in project.stages.filter(client_visible=True).select_related("step_template").order_by("order"):
        action_url, action_label = stage_approval_action(s, invoice)
        stages.append({
            "title": s.client_label or s.title,
            "status": s.status,
            "hint": _duration_hint(s.step_template.estimated_duration_hours),
            "action_url": action_url,
            "action_label": action_label,
        })
    return render(request, "projects/portal_progress.html", {"project": project, "stages": stages})


@login_required
@user_passes_test(_is_technician)
def my_tasks(request):
    return redirect("home")


@login_required
@user_passes_test(_is_technician)
def my_task_detail(request, stage_id):
    stage = get_object_or_404(ProjectStage.objects.select_related("project"), pk=stage_id)
    is_mine = stage.assigned_to_id == request.user.id
    is_candidate = stage.candidate_users.filter(pk=request.user.id).exists()
    if not is_mine and not is_candidate:
        raise Http404
    return _render_staff_project_view(request, stage.project, highlight_stage_id=stage.id)


@login_required
@user_passes_test(_is_technician)
def my_task_claim(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    try:
        claim_stage(stage, request.user)
        messages.success(request, "کار با موفقیت برداشته شد.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@require_POST
def stage_file_upload(request, stage_id):
    stage = get_object_or_404(ProjectStage.objects.select_related("project", "step_template"), pk=stage_id)
    if not can_upload_to_stage(request.user, stage):
        return JsonResponse({"ok": False, "error": "شما اجازه‌ی ارسال فایل در این مرحله را ندارید."}, status=403)
    try:
        f = add_stage_file(stage=stage, uploaded=request.FILES.get("file"), uploader=request.user,
                           cut_count_raw=request.POST.get("cut_count"))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": f.id, "name": f.display_name})


@login_required
@require_POST
def cut_set(request, file_id):
    f = get_object_or_404(ProjectFile.objects.select_related("stage__project"), pk=file_id)
    try:
        set_cut(file=f, index=int(request.POST.get("index", "")), done=request.POST.get("done") == "1",
                actor=request.user)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e) if "int()" not in str(e) else "شماره‌ی برش نامعتبر است."}, status=400)
    total, done = cuts_summary(f.stage.project)
    file_done = f.cuts_done.filter(index__lte=f.cut_count).count()
    return JsonResponse({"ok": True, "total": total, "done": done, "file_done": file_done})


@login_required
@user_passes_test(_is_technician)
def my_task_complete(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    if request.method == "POST":
        needs_approval = {"1": True, "0": False}.get(request.POST.get("needs_approval"))
        try:
            complete_stage(stage=stage, actor=request.user, comment=request.POST.get("comment", "").strip(),
                           needs_approval=needs_approval)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:my_task_detail", stage_id=stage.id)
        messages.success(request, "مرحله با موفقیت تکمیل شد.")
        return redirect("home")
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@user_passes_test(_is_technician)
def my_task_transfer(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    if request.method == "POST":
        target_user = User.objects.filter(pk=request.POST.get("target_user")).first()
        comment = request.POST.get("comment", "").strip()
        if not target_user:
            messages.error(request, "تکنسین انتخاب‌شده معتبر نیست.")
        else:
            try:
                transfer_stage(stage, from_user=request.user, to_user=target_user, comment=comment)
                messages.success(request, f"کار به {target_user.get_full_name() or target_user.username} منتقل شد.")
                return redirect("home")
            except ValueError as e:
                messages.error(request, str(e))
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@user_passes_test(user_can_create_projects)
def new_project_form(request):
    return render(request, "projects/technician_new_project.html", {})


@login_required
@user_passes_test(can_search_parties_for_purchase)
def new_project_party_search(request):
    phone = request.GET.get("phone_number", "").strip()
    prefix = request.GET.get("prefix", "")
    context_role = request.GET.get("context_role", "")
    party = Party.objects.filter(phone_number=phone).first() if phone else None
    return render(request, "projects/partials/technician_party_search_result.html", {
        "phone_number": phone, "party": party, "prefix": prefix, "context_role": context_role,
    })


@login_required
def project_edit(request, project_id):
    project = get_object_or_404(Project.objects.select_related("location", "partner", "owner"), pk=project_id)
    if not can_edit_project(request.user, project):
        raise Http404
    if project.status not in EDITABLE_PROJECT_STATUSES:
        messages.error(request, "پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")
        return redirect("projects:staff_project_overview", project.id)

    if request.method == "POST":
        raw_date = request.POST.get("contract_date")
        if raw_date is None:
            contract_date = NOT_SENT
        elif not raw_date.strip():
            contract_date = None
        else:
            try:
                contract_date = JalaliDateField().clean(raw_date.strip())
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
                return redirect("projects:project_edit", project.id)

        raw_visit = (request.POST.get("visit_date") or "").strip()
        try:
            visit_date = JalaliDateField().clean(raw_visit) if raw_visit else None
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect("projects:project_edit", project.id)

        try:
            with transaction.atomic():
                project, rebuilt = update_project_from_technician_edit(
                    project=project, actor=request.user,
                    location_lat=request.POST.get("latitude") or None,
                    location_lng=request.POST.get("longitude") or None,
                    location_address=request.POST.get("address_text", ""),
                    service_lines=_parse_json_lines_strict(request.POST.get("services_json")),
                    material_lines=_parse_json_lines_strict(request.POST.get("materials_json")),
                    installation_fee_raw=request.POST.get("installation_fee"),
                    shipping_fee_raw=request.POST.get("shipping_fee"),
                    extra_fee_raw=request.POST.get("extra_fee"),
                    contract_date=contract_date,
                    notes=request.POST.get("notes"),
                )
                if visit_date is not None:
                    update_visit_date(project=project, actor=request.user, visit_date=visit_date)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:project_edit", project.id)
        messages.success(request, "تغییرات ذخیره شد و پیش‌فاکتور با مبلغ جدید بازتولید شد." if rebuilt else "تغییرات ذخیره شد.")
        return redirect("projects:staff_project_overview", project.id)

    location = project.location
    visit_stage = project.stages.filter(kind=StageKind.VISIT).first()
    visit_editable = not (visit_stage and visit_stage.status == ProjectStage.Status.DONE)
    visit_date_value = jalali_str(project.visit_date, fmt="%Y/%m/%d") if project.visit_date else ""
    return render(request, "projects/technician_edit_project.html", {
        "project": project,
        "can_price": can_edit_pricing(request.user, project),
        "notes": project.notes or "",
        "visit_date_value": visit_date_value,
        "visit_editable": visit_editable,
        "lat": str(location.latitude) if location and location.latitude is not None else "",
        "lng": str(location.longitude) if location and location.longitude is not None else "",
        "address_text": location.address_text if location else "",
    })


@login_required
@user_passes_test(user_can_create_projects)
def new_project_submit(request):
    if request.method != "POST":
        return redirect("projects:new_project_form")

    ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"

    def fail(message):
        if ajax:
            return JsonResponse({"ok": False, "error": message})
        messages.error(request, message)
        return redirect("projects:new_project_form")

    def done(url, upload_url="", project_url=""):
        if ajax:
            return JsonResponse({"ok": True, "redirect": url, "upload_url": upload_url, "project_url": project_url})
        return redirect(url)

    party_id = request.POST.get("party_id") or None
    party_data = None
    if not party_id:
        roles = request.POST.getlist("roles")
        if not roles:
            return fail("لطفاً حداقل یک نقش (کارفرما، شریک تجاری، پیمانکار یا تأمین‌کننده) را برای طرف‌حساب انتخاب کنید.")
        party_data = {
            "name": request.POST.get("party_name", "").strip(),
            "brand_name": request.POST.get("brand_name", "").strip(),
            "entity_type": request.POST.get("entity_type", "individual"),
            "phone_number": request.POST.get("phone_number", "").strip(),
            "national_code": request.POST.get("national_code", "").strip() or None,
            "is_partner": "partner" in roles,
            "is_client": "client" in roles,
            "is_contractor": "contractor" in roles,
            "is_supplier": "supplier" in roles,
        }

    owner_party_id = None
    owner_party_data = None
    if request.POST.get("different_owner") == "on":
        owner_party_id = request.POST.get("owner_party_id") or None
        if not owner_party_id:
            owner_party_data = {
                "name": request.POST.get("owner_party_name", "").strip(),
                "brand_name": request.POST.get("owner_brand_name", "").strip(),
                "entity_type": request.POST.get("owner_entity_type", "individual"),
                "phone_number": request.POST.get("owner_phone_number", "").strip(),
                "national_code": request.POST.get("owner_national_code", "").strip() or None,
                "is_client": True,
            }
            if not owner_party_data["phone_number"]:
                return fail("شماره‌ی صاحب ملک/کارفرما را وارد کنید یا تیک «صاحب ملک شخص دیگری است» را بردارید.")

    raw_visit = (request.POST.get("visit_date") or "").strip()
    if not raw_visit:
        return fail("تاریخ بازدید را مشخص کنید.")
    try:
        visit_date = JalaliDateField().clean(raw_visit)
    except ValidationError as e:
        return fail(" ".join(e.messages))

    try:
        project, invoice, account_conflict = create_project_from_technician_intake(
            created_by=request.user,
            party_id=party_id, party_data=party_data,
            owner_party_id=owner_party_id, owner_party_data=owner_party_data,
            location_lat=request.POST.get("latitude") or None,
            location_lng=request.POST.get("longitude") or None,
            location_address=request.POST.get("address_text", ""),
            notes=request.POST.get("notes", ""),
            visit_date=visit_date,
            uploaded_files=request.FILES.getlist("project_files"),
            issue_proforma=False,
        )
        messages.success(request, "پروژه ثبت شد.")
        first = project.stages.order_by("order").first()
        return done(
            reverse("home"),
            reverse("projects:stage_file_upload", args=[first.id]) if first else "",
            reverse("projects:staff_project_overview", args=[project.id]),
        )
    except (ValueError, InvalidOperation) as e:
        return fail(str(e))


def _proforma_extra_rows(project):
    return [{"pk": l.pk, "title": l.title, "kind": l.kind, "qty": format(l.qty.normalize(), "f"),
             "unit_price": str(int(l.unit_price))} for l in project.extra_lines.all()]


def _proforma_initial_rows(project):
    def qty_str(v):
        return format(v.normalize(), "f")
    return [
        {"pk": l.pk, "service_id": l.service_id, "qty": qty_str(l.qty), "unit_price": str(int(l.unit_price)),
         "materials": [{"pk": m.pk, "item_id": m.item_id, "qty": qty_str(m.qty)} for m in l.materials.all()]}
        for l in project.services.prefetch_related("materials").order_by("pk")
    ]


@login_required
def proforma_editor(request, project_id):
    project = get_object_or_404(Project.objects.select_related("location", "partner", "owner"), pk=project_id)
    if not can_edit_pricing(request.user, project):
        raise Http404
    if project.status not in EDITABLE_PROJECT_STATUSES:
        messages.error(request, "پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")
        return redirect("projects:staff_project_overview", project.id)

    error = None
    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            raw_date = request.POST.get("contract_date")
            if raw_date is None:
                contract_date = NOT_SENT
            elif not raw_date.strip():
                contract_date = None
            else:
                try:
                    contract_date = JalaliDateField().clean(raw_date.strip())
                except ValidationError as e:
                    raise ValueError(" ".join(e.messages))
            rebuilt = save_proforma(
                project=project, actor=request.user,
                service_rows=parse_service_rows(request.POST.get("services_json")),
                extra_rows=parse_extra_rows(request.POST.get("extras_json")),
                installation_fee_raw=request.POST.get("installation_fee"),
                shipping_fee_raw=request.POST.get("shipping_fee"),
                extra_fee_raw=request.POST.get("extra_fee"),
                contract_date=contract_date,
            )
            if action == "issue":
                invoice, conflict = issue_proforma(
                    project=project, actor=request.user, send_sms=request.POST.get("send_sms") == "on")
                messages.success(request, f"پیش‌فاکتور {invoice.number} صادر شد.")
                if conflict:
                    messages.warning(request, "این شماره موبایل قبلاً برای یک حساب دیگر (مثلاً پرسنل) ثبت شده؛ حساب ورود خودکار ساخته نشد. از پنل ادمین دستی حساب بسازید.")
                return redirect("projects:staff_project_overview", project.id)
            messages.success(request, "ذخیره شد." + (" پیش‌فاکتور با مبلغ جدید بازتولید شد." if rebuilt else ""))
            return redirect("projects:proforma_editor", project.id)
        except ValueError as e:
            error = str(e)
            messages.error(request, error)

    project.refresh_from_db()
    invoice = getattr(project, "invoice", None)
    prices_open = project_prices_editable(project)
    stage = proforma_stage(project)
    can_issue = bool(prices_open and invoice is None and stage
                     and stage.status == ProjectStage.Status.IN_PROGRESS
                     and can_issue_proforma(request.user, stage))

    services, items = _line_choices(project)
    margins = resolve_margin_percents(items)
    initial_rows = _proforma_initial_rows(project)
    initial_extras = _proforma_extra_rows(project)
    costs = _cost_values(project)
    if error:   # خطا = ورودی کاربر گم نشود
        try:
            posted = json.loads(request.POST.get("services_json") or "null")
            if isinstance(posted, list):
                initial_rows = posted
        except (ValueError, TypeError):
            pass
        try:
            posted_ex = json.loads(request.POST.get("extras_json") or "null")
            if isinstance(posted_ex, list):
                initial_extras = posted_ex
        except (ValueError, TypeError):
            pass
        for key in ("installation_fee", "shipping_fee", "extra_fee", "contract_date"):
            if key in request.POST:
                costs[key] = request.POST.get(key, "")

    stale = []
    if prices_open:
        mats = [m for l in project.services.prefetch_related("materials__item") for m in l.materials.all()]
        now_margin = resolve_margin_percents({m.item for m in mats})
        stale = sorted({
            m.item.name for m in mats
            if m.cost_snapshot != m.item.moving_average_cost
            or m.margin_percent != Decimal(now_margin[m.item_id]).quantize(Decimal("0.01"))
        })

    return render(request, "projects/proforma_editor.html", {
        "project": project, "invoice": invoice, "stage": stage,
        "prices_open": prices_open, "can_issue": can_issue,
        "services_data": [{"id": s.id, "name": s.name, "unit": s.get_unit_display() if s.unit else ""} for s in services],
        "items_data": [{"id": i.id, "name": i.name, "unit": i.get_unit_display(),
                        "cost": str(i.moving_average_cost), "margin": str(margins[i.pk])} for i in items],
        "initial_rows": initial_rows, "initial_extras": initial_extras, "costs": costs,
        "extra_lines": project.extra_lines.all(),
        "participants_cost": project.participants.aggregate(t=Sum("agreed_cost"))["t"] or 0,
        "has_global_margin": has_global_margin(),
        "lines": project.services.select_related("service").prefetch_related("materials__item"),
        "stale_items": stale,
    })
