from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from inventory.models import PurchaseLine, StockMovement
from projects import ops
from projects.models import Project, StageKind
from projects.services import user_can_access_accounting
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits
from utils.utils import separate_digits

from . import accounting

PROJECT_STATUS_VARIANT = {"completed": "success", "cancelled": "error", "in_progress": "info"}


def _can(user):
    return user_can_access_accounting(user)


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
    })


def _table_page(request, builder, *, nav, title, sub):
    ctx = builder(request)
    ctx.update(nav_active=nav, page_title=title, page_sub=sub)
    return render(request, "finance/accounting_table_page.html", ctx)


# ---------- جدول پروژه‌ها ----------
def _projects_ctx(request):
    qs = accounting.projects_financial_queryset().order_by("-created_at")

    def row_builder(p):
        profit_variant = "success" if p.profit > 0 else ("error" if p.profit < 0 else "neutral")
        return {"url": reverse("finance:accounting_project", args=[p.id]), "cells": [
            {"type": "text", "value": p.name},
            {"type": "muted", "value": to_fa_digits(p.code)},
            {"type": "badge", "value": p.get_status_display(), "variant": PROJECT_STATUS_VARIANT.get(p.status, "neutral")},
            {"type": "text", "value": _m(p.revenue)},
            {"type": "text", "value": _m(p.remaining)},
            {"type": "text", "value": _m(p.actual_cost)},
            {"type": "badge", "value": _m(p.profit), "variant": profit_variant},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "پروژه", "sort_field": "name"},
            {"label": "کد", "sort_field": "code"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": Project.Status.choices},
            {"label": "فروش (تومان)", "sort_field": "revenue", "filter_key": "revenue", "filter_type": "number_range"},
            {"label": "مانده‌ی فاکتور (تومان)", "sort_field": "remaining", "filter_key": "remaining", "filter_type": "number_range"},
            {"label": "هزینه‌ی ثبت‌شده (تومان)", "sort_field": "actual_cost"},
            {"label": "سود ثبت‌شده (تومان)", "sort_field": "profit", "filter_key": "profit", "filter_type": "number_range"},
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
            project_cell = {"type": "link", "value": related.name, "url": reverse("finance:accounting_project", args=[related.id])}
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
            {"label": "تأمین‌کننده", "sort_field": "purchase__supplier__name"},
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
def project_detail(request, project_id):
    project = get_object_or_404(accounting.projects_financial_queryset(), pk=project_id)
    invoice = getattr(project, "invoice", None)
    recon = accounting.project_reconciliation(project)
    return render(request, "finance/accounting_project.html", {
        "nav_active": "projects", "project": project, "invoice": invoice,
        "payments": invoice.payments.order_by("-created_at") if invoice else [],
        "recon": recon, "unsettled_count": sum(1 for r in recon if r["status"] != "ok"),
        "data": ops.final_review_data(project),
        "moves": accounting.project_movements(project),
        "stock_net": project.stock_out - project.stock_back,
        "planned_hint": f"طبق پیش‌فاکتور: {_m(project.planned_cost)} تومان",
        "has_final_review": project.stages.filter(kind=StageKind.FINAL_REVIEW).exists(),
    })