from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Case, IntegerField, When
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from catalog.models import Item
from inventory.services import user_can_manage_inventory, record_manual_stock_change
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits
from . import ops
from .models import ExtraShipment, InstallLine, PartRequest, Project, ProjectFile, ProjectStage, StageKind
from .stage_ops import complete_stage
from .stage_move import move_to_stage


def _json(action):
    try:
        data = action()
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, **(data or {})})


def _obj(model, raw, **kw):
    try:
        return get_object_or_404(model, pk=int(raw), **kw)
    except (TypeError, ValueError):
        raise Http404


@login_required
@require_POST
def ship_check(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    f = _obj(ProjectFile.objects.select_related("stage"), request.POST.get("file_id"))
    return _json(lambda: ops.set_shipment_check(stage=stage, file=f, status=request.POST.get("status"),
                                                reason=request.POST.get("reason"), actor=request.user))


@login_required
@require_POST
def install_line(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    line = _obj(InstallLine, request.POST.get("line_id"), stage=stage)
    def run():
        l = ops.set_install_line(line=line, status=request.POST.get("status"),
                                 actual_qty_raw=request.POST.get("qty"), reason=request.POST.get("reason"), actor=request.user)
        pending = stage.install_lines.filter(status=InstallLine.Status.PENDING).count()
        return {"pending": pending, "delta": str(l.delta_qty) if l.delta_qty is not None else ""}
    return _json(run)


@login_required
@require_POST
def extra_add(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    return _json(lambda: ops.add_extra_shipment(stage=stage, item_id=request.POST.get("item_id"),
                                                qty_raw=request.POST.get("qty"), note=request.POST.get("note"), actor=request.user) and None)


@login_required
@require_POST
def extra_delete(request, extra_id):
    extra = _obj(ExtraShipment.objects.select_related("stage__project", "item"), extra_id)
    return _json(lambda: ops.delete_extra_shipment(extra=extra, actor=request.user))


@login_required
@require_POST
def part_request_create(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    return _json(lambda: ops.create_part_request(stage=stage, item_id=request.POST.get("item_id"),
                                                 qty_raw=request.POST.get("qty"), note=request.POST.get("note"), actor=request.user) and None)


@login_required
@require_POST
def part_request_cancel(request, req_id):
    req = _obj(PartRequest, req_id)
    return _json(lambda: ops.cancel_part_request(req=req, actor=request.user))


# ----- انباردار -----
def part_requests_table_context(request):
    qs = PartRequest.objects.select_related("project", "item", "requested_by").annotate(
        rank=Case(When(status=PartRequest.Status.REQUESTED, then=0), default=1, output_field=IntegerField())
    ).order_by("rank", "-requested_at")
    variant = {"requested": "warning", "issued": "success", "rejected": "error", "cancelled": "neutral"}

    def row_builder(p):
        return {"url": reverse("projects:part_request_detail", args=[p.id]), "cells": [
            {"type": "text", "value": p.project.name},
            {"type": "text", "value": p.item.name},
            {"type": "muted", "value": to_fa_digits(format(p.qty.normalize(), "f"))},
            {"type": "muted", "value": (p.requested_by.get_full_name() or p.requested_by.username) if p.requested_by else "—"},
            {"type": "muted", "value": jalali_str(p.requested_at, fmt="%Y/%m/%d %H:%M")},
            {"type": "badge", "value": p.get_status_display(), "variant": variant.get(p.status, "neutral")},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "پروژه", "sort_field": "project__name"}, {"label": "کالا", "sort_field": "item__name"},
            {"label": "مقدار"}, {"label": "درخواست‌کننده"}, {"label": "تاریخ", "sort_field": "requested_at"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": PartRequest.Status.choices},
        ],
        row_builder=row_builder, container_id="table-part-requests", param_prefix="pq_",
        empty_icon="package", empty_text="درخواست قطعه‌ای ثبت نشده.",
        list_url=reverse("projects:part_requests_table"), search_fields=["project__name", "item__name"],
    )


@login_required
@user_passes_test(user_can_manage_inventory)
def part_requests_table(request):
    return render_table(request, part_requests_table_context(request))


@login_required
@user_passes_test(user_can_manage_inventory)
def part_request_detail(request, req_id):
    from core.capabilities import can
    req = _obj(PartRequest.objects.select_related("project", "item", "requested_by", "stage"), req_id)
    return render(request, "projects/part_request_detail.html", {
        "req": req, "stock": req.item.current_stock, "show_money": can(request.user, "money.view"),
    })


@login_required
@user_passes_test(user_can_manage_inventory)
@require_POST
def part_request_decide(request, req_id):
    req = _obj(PartRequest, req_id)
    try:
        if request.POST.get("action") == "issue":
            ops.issue_part_request(
                req=req,
                actor=request.user,
                shipping_cost_raw=request.POST.get("shipping_cost", ""),
                photo=request.FILES.get("photo"),
            )
            messages.success(request, "قطعه تحویل و از انبار کم شد.")
        elif request.POST.get("action") == "reject":
            ops.reject_part_request(req=req, actor=request.user, reason=request.POST.get("reason"))
            messages.warning(request, "درخواست رد شد.")
        else:
            messages.error(request, "عملیات نامعتبر است.")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("projects:part_request_detail", req.id)
    return redirect("home")


def _settlement_input(post):
    from finance import accounting
    qtys, reasons = {}, {}
    for key, value in post.items():
        try:
            if key.startswith("final_qty_") and value.strip():
                qtys[int(key[len("final_qty_"):])] = accounting.parse_qty(value, label="مصرف نهایی")
            elif key.startswith("reason_"):
                reasons[int(key[len("reason_"):])] = value
        except ValueError as e:
            if "مصرف نهایی" in str(e):
                raise
    return qtys, reasons


@login_required
def final_review(request, project_id):
    project = _obj(Project.objects.select_related("owner", "partner", "location"), project_id)
    if not ops.can_view_final_review(request.user, project):
        raise Http404
    stage = project.stages.filter(kind=StageKind.FINAL_REVIEW).first()
    if stage is None:
        raise Http404
    from finance import accounting
    if request.method == "POST":
        try:
            with transaction.atomic():
                qtys, reasons = _settlement_input(request.POST)
                complete_stage(stage=stage, actor=request.user, comment=(request.POST.get("comment") or "").strip(), via_review=True)
                accounting.settle_project_materials(project=project, final_qtys=qtys, reasons=reasons, actor=request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:final_review", project.id)
        messages.success(request, "بازبینی نهایی تایید، مصرف مواد ثبت و پروژه تکمیل شد.")
        return redirect("home")
    fin = accounting.projects_financial_queryset().get(pk=project.pk)
    recon = accounting.project_reconciliation(project)
    return render(request, "projects/final_review.html", {
        "project": project, "stage": stage, "can_approve": stage.status == ProjectStage.Status.IN_PROGRESS,
        "invoice": getattr(project, "invoice", None), "data": ops.final_review_data(project),
        "recon": recon, "pnl": accounting.project_pnl(fin),
        "stock_items": [{"id": i.id, "name": i.name, "unit": i.get_unit_display()} for i in Item.objects.filter(is_active=True)],
    })


@login_required
@require_POST
def final_review_consume(request, project_id):
    project = _obj(Project, project_id)
    if not ops.can_view_final_review(request.user, project):
        raise Http404
    from finance import accounting
    from inventory.services import get_active_item
    try:
        item = get_active_item(request.POST.get("item_id"))
        if item.pk in {r["item"].pk for r in accounting.project_reconciliation(project)}:
            raise ValueError("این کالا در جدول تسویه هست؛ مقدارش را همان‌جا تغییر دهید.")
        qty = request.POST.get("qty")
        notes = (request.POST.get("notes") or "").strip()
        record_manual_stock_change(item=item, kind="consume", qty_raw=qty, notes=notes,
                                   user=request.user, related_object=project)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        accounting.log_event(kind="stock_fix", project=project, actor=request.user,
                             text=f"مصرف کالای دیگر: {item.name} × {qty} — {notes}")
        messages.success(request, "مصرف ثبت شد؛ کالا به جدول تسویه اضافه شد.")
    return redirect("projects:final_review", project.id)


@login_required
@require_POST
def move_stage(request, project_id):
    project = _obj(Project, project_id)
    try:
        target = move_to_stage(
            project=project, target_id=request.POST.get("target"),
            actor=request.user, comment=request.POST.get("comment"),
            return_to_current=request.POST.get("return_mode") != "continue",
        )
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"مرحله‌ی «{target.title}» باز شد.")
    return redirect("projects:staff_project_overview", project.id)
