from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from core.capabilities import can, cap_required
from core.models import Party
from projects.services import project_prices_editable
from django.utils.http import url_has_allowed_host_and_scheme

from inventory.models import PurchaseLine, StockMovement
from projects import ops
from projects.models import Project, ProjectCost, StageKind
from utils.jalali_forms import JalaliDateField
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits
from utils.utils import separate_digits

from . import accounting
from .services import cancel_invoice, set_invoice_due_date

PROJECT_STATUS_VARIANT = {"completed": "success", "cancelled": "error", "in_progress": "info"}


def _can(user):
    return can(user, "accounting.access")


def _can_unlock(user):
    return can(user, "periods.unlock")


def _m(value):
    return to_fa_digits(separate_digits(value))


def _q(value):
    return to_fa_digits(format(value.normalize(), "f"))


# ---------- نمای کلی ----------
@login_required
@user_passes_test(_can)
def overview(request):
    period = request.GET.get("period", "all")
    if period not in dict(accounting.PERIODS):
        period = "all"
    return render(request, "finance/accounting_overview.html", {
        "nav_active": "overview", "periods": accounting.PERIODS, "period": period,
        "stats": accounting.accounting_overview(period),
        "attention": accounting.attention_items(),
        "review_queue": accounting.final_review_queue(),
        "proforma_queue": accounting.proforma_queue(),
    })


def _table_page(request, builder, *, nav, title, sub):
    ctx = builder(request)
    ctx.update(nav_active=nav, page_title=title, page_sub=sub)
    return render(request, "finance/accounting_table_page.html", ctx)


# ---------- جدول پروژه‌ها ----------
def _projects_ctx(request):
    qs = accounting.projects_financial_queryset().order_by("-created_at")

    def row_builder(p):
        from utils.navigation import nav_reverse
        return {"url": nav_reverse(request, "finance:accounting_project", args=[p.id]), "cells": [
            {"type": "text", "value": p.name},
            {"type": "muted", "value": to_fa_digits(p.code)},
            {"type": "badge", "value": p.get_status_display(), "variant": PROJECT_STATUS_VARIANT.get(p.status, "neutral")},
            {"type": "text", "value": _m(p.revenue)},
            {"type": "text", "value": _m(p.paid)},
            {"type": "text", "value": _m(p.remaining)},
            {"type": "text", "value": _m(p.actual_cost)},
            {"type": "text", "value": _m(p.net_result)},
            {"type": "badge", "value": "بعد از تسویه" if p.final_done else "موقت", "variant": "neutral"},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "پروژه", "sort_field": "name"},
            {"label": "کد", "sort_field": "code"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": Project.Status.choices},
            {"label": "فروش (تومان)", "sort_field": "revenue", "filter_key": "revenue", "filter_type": "number_range"},
            {"label": "دریافتی (تومان)", "sort_field": "paid"},
            {"label": "مانده‌ی فاکتور (تومان)", "sort_field": "remaining", "filter_key": "remaining", "filter_type": "number_range"},
            {"label": "هزینه‌ی ثبت‌شده (تومان)", "sort_field": "actual_cost"},
            {"label": "فروش منهای هزینه‌ها (تومان)", "sort_field": "net_result", "filter_key": "net_result", "filter_type": "number_range"},
            {"label": "حساب", "sort_field": "final_done", "filter_key": "final", "filter_type": "boolean",
             "filter_field": "final_done", "true_label": "بعد از تسویه", "false_label": "موقت"},
        ],
        row_builder=row_builder, container_id="table-acc-projects", param_prefix="ap_",
        empty_icon="folder-kanban", empty_text="هنوز پروژه‌ای ثبت نشده.",
        list_url=reverse("finance:accounting_projects_table"),
        search_fields=["name", "code", "owner__name", "partner__name"],
        search_placeholder="جستجو در نام پروژه، کد یا طرف‌حساب...",
    )


@login_required
@user_passes_test(_can)
def projects_page(request):
    return _table_page(request, _projects_ctx, nav="projects", title="پروژه‌ها",
                       sub="وضعیت مالی همه‌ی پروژه‌ها. برای دیدن پرونده‌ی کامل روی هر ردیف بزنید.")


@login_required
@user_passes_test(_can)
def projects_table(request):
    return render_table(request, _projects_ctx(request))


# ---------- حرکات انبار ----------
def _stock_ctx(request):
    qs = StockMovement.objects.select_related("item", "created_by").prefetch_related("related_object").order_by("-created_at", "-id")

    def row_builder(m):
        related = m.related_object
        if isinstance(related, Project):
            from utils.navigation import nav_reverse
            project_cell = {"type": "link", "value": related.name, "url": nav_reverse(request, "finance:accounting_project", args=[related.id])}
        else:
            project_cell = {"type": "muted", "value": "—"}
        return {"url": None, "cells": [
            {"type": "muted", "value": jalali_str(m.created_at, fmt="%Y/%m/%d %H:%M")},
            {"type": "text", "value": m.item.name},
            {"type": "badge", "value": m.get_movement_type_display(), "variant": "neutral"},
            {"type": "badge", "value": m.get_direction_display(),
             "variant": "success" if m.direction == StockMovement.Direction.IN else "warning"},
            {"type": "muted", "value": _q(m.qty)},
            {"type": "text", "value": _m(m.qty * m.unit_cost)},
            project_cell,
            {"type": "muted", "value": (m.created_by.get_full_name() or m.created_by.username) if m.created_by else "—"},
            {"type": "muted", "value": m.notes or "—"},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "تاریخ", "sort_field": "created_at"},
            {"label": "کالا", "sort_field": "item__name"},
            {"label": "نوع", "sort_field": "movement_type", "filter_key": "type", "filter_type": "select",
             "filter_field": "movement_type", "choices": StockMovement.MovementType.choices},
            {"label": "اثر", "sort_field": "direction", "filter_key": "direction", "filter_type": "select",
             "choices": StockMovement.Direction.choices},
            {"label": "مقدار"},
            {"label": "ارزش (تومان)"},
            {"label": "پروژه"},
            {"label": "ثبت‌کننده"},
            {"label": "دلیل"},
        ],
        row_builder=row_builder, container_id="table-acc-stock", param_prefix="al_",
        empty_icon="package", empty_text="هنوز حرکتی در انبار ثبت نشده.",
        list_url=reverse("finance:accounting_stock_table"),
        search_fields=["item__name", "notes"], search_placeholder="جستجو در کالا یا دلیل...",
    )


@login_required
@user_passes_test(_can)
def stock_page(request):
    return _table_page(request, _stock_ctx, nav="stock", title="حرکات انبار",
                       sub="همه‌ی ورود و خروج‌ها. موجودی اولیه و تعدیل‌ها خرید حساب نمی‌شوند.")


@login_required
@user_passes_test(_can)
def stock_table(request):
    return render_table(request, _stock_ctx(request))


# ---------- خریدها ----------
def _purchases_ctx(request):
    qs = (PurchaseLine.objects.select_related("purchase__supplier", "item")
          .annotate(line_total=accounting.VALUE).order_by("-purchase__purchased_at", "-id"))

    def row_builder(l):
        return {"url": None, "cells": [
            {"type": "muted", "value": jalali_str(l.purchase.purchased_at, fmt="%Y/%m/%d")},
            {"type": "text", "value": l.purchase.supplier.name},
            {"type": "muted", "value": to_fa_digits(l.purchase.invoice_number) or "—"},
            {"type": "text", "value": l.item.name},
            {"type": "muted", "value": _q(l.qty)},
            {"type": "muted", "value": _m(l.unit_cost)},
            {"type": "text", "value": _m(l.line_total)},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "تاریخ", "sort_field": "purchase__purchased_at"},
            {"label": "تأمین‌کننده", "sort_field": "purchase__supplier__name", "filter_key": "supplier",
             "filter_type": "select", "filter_field": "purchase__supplier_id",
             "choices": [(p.id, p.name) for p in Party.objects.filter(purchases__isnull=False).distinct().order_by("name")]},
            {"label": "شماره فاکتور"},
            {"label": "کالا", "sort_field": "item__name"},
            {"label": "مقدار"},
            {"label": "بهای واحد (تومان)"},
            {"label": "جمع (تومان)", "sort_field": "line_total", "filter_key": "total", "filter_type": "number_range",
             "filter_field": "line_total"},
        ],
        row_builder=row_builder, container_id="table-acc-purchases", param_prefix="au_",
        empty_icon="receipt", empty_text="هنوز خریدی ثبت نشده.",
        list_url=reverse("finance:accounting_purchases_table"),
        search_fields=["purchase__supplier__name", "purchase__invoice_number", "item__name"],
        search_placeholder="جستجو در تأمین‌کننده، شماره فاکتور یا کالا...",
    )


@login_required
@user_passes_test(_can)
def purchases_page(request):
    return _table_page(request, _purchases_ctx, nav="purchases", title="خریدها",
                       sub="فقط خریدهای ثبت‌شده با فاکتور خرید. موجودی اولیه اینجا نیست.")


@login_required
@user_passes_test(_can)
def purchases_table(request):
    return render_table(request, _purchases_ctx(request))


# ---------- پرونده‌ی مالی پروژه ----------
@login_required
@user_passes_test(_can)
@require_POST
def project_add_cost(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    try:
        cost = ops.add_project_cost(project=project, kind=request.POST.get("kind"), title=request.POST.get("title"),
                                    amount_raw=request.POST.get("amount"), actor=request.user)
        accounting.log_event(kind="cost", project=project, actor=request.user, amount=cost.amount,
                             text=f"هزینه ثبت شد: {cost.title}")
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "هزینه ثبت شد.")
    return redirect("finance:accounting_project", project.id)


@login_required
@user_passes_test(_can)
@require_POST
def project_delete_cost(request, cost_id):
    from projects.models import ProjectCost
    cost = get_object_or_404(ProjectCost.objects.select_related("project"), pk=cost_id)
    reason = (request.POST.get("reason") or "").strip()
    try:
        if not reason:
            raise ValueError("دلیل حذف را بنویسید.")
        title, amount, project = cost.title, cost.amount, cost.project
        ops.delete_project_cost(cost=cost, actor=request.user)
        accounting.log_event(kind="cost", project=project, actor=request.user, amount=-amount,
                             text=f"هزینه حذف شد: {title} — {reason}")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("finance:accounting_project", cost.project_id)
    messages.success(request, "هزینه حذف شد.")
    return redirect("finance:accounting_project", project.id)


@login_required
@user_passes_test(_can)
@require_POST
def project_adjust_invoice(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    invoice = getattr(project, "invoice", None)
    try:
        if invoice is None:
            raise ValueError("این پروژه فاکتور ندارد.")
        accounting.add_invoice_adjustment(
            invoice=invoice, title=request.POST.get("title"), amount_raw=request.POST.get("amount"),
            kind=request.POST.get("kind"), reason=request.POST.get("reason"), actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "ردیف به فاکتور اضافه شد.")
    return redirect("finance:accounting_project", project.id)


@login_required
@user_passes_test(_can)
@require_POST
def project_add_payment(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    invoice = getattr(project, "invoice", None)
    try:
        if invoice is None:
            raise ValueError("این پروژه فاکتور ندارد.")
        raw_date = (request.POST.get("paid_date") or "").strip()
        try:
            paid_date = JalaliDateField().clean(raw_date) if raw_date else None
        except ValidationError as e:
            raise ValueError(" ".join(e.messages))
        accounting.record_accountant_payment(
            invoice=invoice, method=request.POST.get("method"), amount_raw=request.POST.get("amount"),
            paid_date=paid_date, reference_number=request.POST.get("reference_number"),
            note=request.POST.get("note"), receipt_file=request.FILES.get("receipt_file"),
            cheque_number=request.POST.get("cheque_number", ""), cheque_bank=request.POST.get("cheque_bank", ""),
            actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "پرداخت ثبت شد.")
    return redirect("finance:accounting_project", project.id)


@login_required
@user_passes_test(_can)
@require_POST
def project_set_due(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    invoice = getattr(project, "invoice", None)
    try:
        if invoice is None:
            raise ValueError("این پروژه فاکتور ندارد.")
        raw = (request.POST.get("due_date") or "").strip()
        try:
            due = JalaliDateField().clean(raw) if raw else None
        except ValidationError as e:
            raise ValueError(" ".join(e.messages))
        set_invoice_due_date(invoice=invoice, due_date=due, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "سررسید ثبت شد." if due else "سررسید پاک شد.")
    return redirect("finance:accounting_project", project.id)


@login_required
@user_passes_test(_can)
@require_POST
def project_cancel_invoice(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    invoice = getattr(project, "invoice", None)
    try:
        if invoice is None:
            raise ValueError("این پروژه فاکتور ندارد.")
        cancel_invoice(invoice=invoice, reason=request.POST.get("reason"), actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "فاکتور لغو شد.")
    return redirect("finance:accounting_project", project.id)



def _period_rows(count=14):
    return accounting.period_rows(count)


@login_required
@user_passes_test(_can)
def periods_page(request):
    return render(request, "finance/accounting_periods.html", {
        "nav_active": "periods", "periods": _period_rows(), "can_unlock": _can_unlock(request.user),
    })


def _back(request, default_name):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(
            nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(default_name)


@login_required
@user_passes_test(_can)
@require_POST
def period_toggle(request):
    try:
        year, month = int(request.POST.get("year", "")), int(request.POST.get("month", ""))
    except ValueError:
        messages.error(request, "ماه نامعتبر است.")
        return _back(request, "finance:accounting_periods")
    action = request.POST.get("action")
    reason = (request.POST.get("reason") or "").strip()
    from core.periods import set_lock, month_label
    try:
        if action == "lock":
            set_lock(year, month, locked=True, user=request.user)
            accounting.log_event(kind="period", actor=request.user, text=f"بستن ماه {month_label(year, month)}")
            messages.success(request, f"ماه {month_label(year, month)} بسته شد.")
        elif action == "unlock":
            if not _can_unlock(request.user):
                raise ValueError("فقط مدیر می‌تواند ماه را باز کند.")
            if not reason:
                raise ValueError("دلیل بازکردن ماه اجباری است.")
            set_lock(year, month, locked=False, user=request.user)
            accounting.log_event(kind="period", actor=request.user,
                                 text=f"بازکردن ماه {month_label(year, month)} — دلیل: {reason}")
            messages.success(request, f"ماه {month_label(year, month)} باز شد.")
        else:
            raise ValueError("عملیات نامعتبر است.")
    except ValueError as e:
        messages.error(request, str(e))
    return _back(request, "finance:accounting_periods")



@login_required
@user_passes_test(_can)
def financial_report_page(request):
    from finance.reports import get_jalali_date_range, generate_periodic_financial_report
    from utils.exporters import export_report_to_csv
    
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    export_format = request.GET.get("export", "")

    report = None
    error_msg = None
    
    if start_date and end_date:
        try:
            start_g, end_g = get_jalali_date_range(start_date, end_date)
            report = generate_periodic_financial_report(start_g, end_g)
            
            if export_format == "csv":
                return export_report_to_csv(report)
        except ValueError as e:
            error_msg = str(e)
            
    return render(request, "finance/accounting_report.html", {
        "nav_active": "reports",
        "report": report,
        "error_msg": error_msg,
        "start_date": start_date,
        "end_date": end_date,
    })


@login_required
@user_passes_test(_can)
def customers_center_page(request):
    from finance.aging import get_customer_aging_data
    from finance.models import Payment

    selected_client = aging_summary = aging_rows = payments = None
    client_id = (request.GET.get("client_id") or "").strip()
    if client_id:
        if not client_id.isdigit():
            raise Http404
        selected_client = get_object_or_404(
            Party.objects.filter(is_internal=False, invoices__isnull=False).distinct(), pk=int(client_id))
        aging_summary, aging_rows = get_customer_aging_data(selected_client)
        payments = (Payment.objects.filter(invoice__billed_party=selected_client)
                    .select_related("invoice").order_by("-created_at")[:50])

    return render(request, "finance/accounting_customers.html", {
        "nav_active": "customers", "selected_client": selected_client,
        "aging_summary": aging_summary, "aging_rows": aging_rows, "payments": payments,
    })


# ---------- تأمین‌کننده‌ها ----------
def _suppliers_ctx(request):
    qs = (Party.objects.annotate(purchases_count=Count("purchases", distinct=True),
                                 total=Sum(accounting.SUPPLIER_VALUE),
                                 last_at=Max("purchases__purchased_at"))
          .filter(purchases_count__gt=0).order_by("-last_at"))

    def row_builder(p):
        return {"url": reverse("finance:accounting_supplier", args=[p.id]), "cells": [
            {"type": "text", "value": p.name},
            {"type": "muted", "value": to_fa_digits(p.phone_number) or "—"},
            {"type": "muted", "value": to_fa_digits(p.purchases_count)},
            {"type": "text", "value": _m(p.total)},
            {"type": "muted", "value": jalali_str(p.last_at, fmt="%Y/%m/%d")},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "تأمین‌کننده", "sort_field": "name"},
            {"label": "تلفن"},
            {"label": "تعداد خرید", "sort_field": "purchases_count"},
            {"label": "جمع خرید (تومان)", "sort_field": "total", "filter_key": "total", "filter_type": "number_range"},
            {"label": "آخرین خرید", "sort_field": "last_at"},
        ],
        row_builder=row_builder, container_id="table-acc-suppliers", param_prefix="as_",
        empty_icon="receipt", empty_text="هنوز خریدی از تأمین‌کننده‌ای ثبت نشده.",
        list_url=reverse("finance:accounting_suppliers_table"),
        search_fields=["name", "phone_number"], search_placeholder="جستجو در نام یا شماره تأمین‌کننده...",
    )


@login_required
@user_passes_test(_can)
def suppliers_page(request):
    return _table_page(request, _suppliers_ctx, nav="suppliers", title="تأمین‌کننده‌ها",
                       sub="از هر تأمین‌کننده چقدر و چه چیزی خریده‌ایم. فقط برای آمار؛ حسابی با تأمین‌کننده نگهداری نمی‌شود.")


@login_required
@user_passes_test(_can)
def suppliers_table(request):
    return render_table(request, _suppliers_ctx(request))


@login_required
@user_passes_test(_can)
def supplier_detail(request, party_id):
    party = get_object_or_404(Party, pk=party_id)
    lines = PurchaseLine.objects.filter(purchase__supplier=party)
    return render(request, "finance/accounting_supplier.html", {
        "nav_active": "suppliers", "party": party, "items": accounting.supplier_items(party),
        "purchases_count": party.purchases.count(),
        "total": accounting._sum(lines, accounting.VALUE),
    })


@login_required
@user_passes_test(_can)
def project_detail(request, project_id):
    project = get_object_or_404(accounting.projects_financial_queryset(), pk=project_id)
    invoice = getattr(project, "invoice", None)
    recon = accounting.project_reconciliation(project)
    return render(request, "finance/accounting_project.html", {
        "nav_active": "projects", "project": project, "invoice": invoice,
        "payments": invoice.payments.order_by("-created_at") if invoice else [],
        "recon": recon, "unsettled_count": sum(1 for r in recon if r["status"] != "ok"),
        "pnl": accounting.project_pnl(project),
        "data": ops.final_review_data(project),
        "moves": accounting.project_movements(project),
        "events": project.accounting_events.select_related("actor")[:50],
        "can_adjust_invoice": bool(invoice and not project_prices_editable(project)),
        "has_final_review": project.stages.filter(kind=StageKind.FINAL_REVIEW).exists(),
        "cost_kinds": ProjectCost.Kind.choices,
        "due_value": jalali_str(invoice.due_date, fmt="%Y/%m/%d") if invoice and invoice.due_date else "",
    })