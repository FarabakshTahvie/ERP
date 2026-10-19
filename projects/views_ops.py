from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from catalog.models import Item
from inventory.services import record_manual_stock_change
from . import ops, usage
from .models import Project, ProjectStage, StageKind
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
def usage_set(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    return _json(lambda: usage.set_usage(stage=stage, item_id=request.POST.get("item_id"),
                                         qty_raw=request.POST.get("qty"), actor=request.user))


@login_required
@require_POST
def install_service_set(request, stage_id):
    stage = _obj(ProjectStage.objects.select_related("project"), stage_id)
    return _json(lambda: usage.set_service_done(stage=stage, service_line_id=request.POST.get("service_id"),
                                                done=request.POST.get("done") == "1", actor=request.user))


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


def _cover_input(post):
    """کالاهایی که حسابدار «کسری انبار را ثبت کن» را برایشان زده: {item_id}."""
    out = set()
    for key, value in post.items():
        if key.startswith("cover_") and value == "1":
            try:
                out.add(int(key[len("cover_"):]))
            except ValueError:
                pass
    return out


@login_required
def final_review(request, project_id):
    project = _obj(Project.objects.select_related("owner", "partner", "location"), project_id)
    if not ops.can_view_final_review(request.user, project):
        raise Http404
    stage = project.stages.filter(kind=StageKind.FINAL_REVIEW).first()
    if stage is None:
        raise Http404
    from finance import accounting
    from finance.services import finalize_invoice
    if request.method == "POST":
        finalized = False
        try:
            with transaction.atomic():
                qtys, reasons = _settlement_input(request.POST)
                complete_stage(stage=stage, actor=request.user, comment=(request.POST.get("comment") or "").strip(), via_review=True)
                accounting.settle_project_materials(project=project, final_qtys=qtys, reasons=reasons,
                                                    actor=request.user, cover=_cover_input(request.POST))
                invoice = getattr(project, "invoice", None)
                if invoice is not None:
                    finalized = finalize_invoice(invoice=invoice, actor=request.user) is not None
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:final_review", project.id)
        messages.success(request, "بازبینی نهایی تایید، مصرف مواد ثبت و پروژه تکمیل شد."
                         + (" پیش‌فاکتور به فاکتور تبدیل شد." if finalized else ""))
        return redirect("home")
    fin = accounting.projects_financial_queryset().get(pk=project.pk)
    recon = accounting.project_reconciliation(project)
    can_approve = stage.status == ProjectStage.Status.IN_PROGRESS and project.status == Project.Status.IN_PROGRESS
    can_suspend = stage.status == ProjectStage.Status.IN_PROGRESS and project.status == Project.Status.IN_PROGRESS
    can_cancel_now = project.status == Project.Status.IN_PROGRESS
    return render(request, "projects/final_review.html", {
        "project": project, "stage": stage,
        "can_approve": can_approve,
        "can_suspend": can_suspend,
        "can_cancel_now": can_cancel_now,
        "invoice": getattr(project, "invoice", None), "data": ops.final_review_data(project),
        "recon": recon, "shortfalls": [r for r in recon if r["stock_short"]], "pnl": accounting.project_pnl(fin),
        "usage_stages": usage.project_usage_by_stage(project),
        "breakdown": ops.proforma_breakdown(project),
        "events": project.accounting_events.select_related("actor")[:50],
        "moves": accounting.project_movements(project),
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

