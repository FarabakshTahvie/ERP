import io
import json
from decimal import Decimal

import weasyprint
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.capabilities import cap_required
from inventory import sales as sales_svc
from inventory.models import Sale, SalePayment, Warehouse
from inventory.services import stock_by_warehouse, stockable_items
from utils.generic_table import render_table
from utils.jalali_forms import JalaliDateField

from .views_accounting import _sales_ctx

DETAIL = "finance:accounting_sale"
FORM = "finance/accounting_sale_form.html"


def _lines_json(post):
    """None = ارسال نشده (دست نزن). JSON خراب = لیست خالی (سرویس خطای فارسی می‌دهد)."""
    raw = post.get("lines_json")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return JalaliDateField().clean(raw)
    except ValidationError as e:
        raise ValueError(" ".join(e.messages))


def _form_context(sale, post):
    items = list(stockable_items().order_by("name"))
    if sale is not None:
        known = {i.pk for i in items}
        items += [l.item for l in sale.lines.select_related("item") if l.item_id not in known]
    stock = stock_by_warehouse(i.pk for i in items)
    if post is not None:
        values = {"name": post.get("customer_name", ""), "phone": post.get("customer_phone", ""),
                  "notes": post.get("notes", ""), "pay_amount": post.get("pay_amount", ""),
                  "pay_method": post.get("pay_method", "cash")}
        lines = _lines_json(post) or []
    elif sale is not None:
        values = {"name": sale.customer_name, "phone": sale.customer_phone,
                  "notes": sale.notes, "pay_amount": "", "pay_method": "cash"}
        lines = [{"id": l.item_id, "qty": format(l.qty.normalize(), "f"), "unit_price": str(int(l.unit_price)),
                  "warehouse_id": l.warehouse_id} for l in sale.lines.order_by("pk")]
    else:
        values = {"name": "", "phone": "", "notes": "", "pay_amount": "", "pay_method": "cash"}
        lines = []
    return {
        "nav_active": "sales", "sale": sale, "values": values, "initial_lines": lines,
        "warehouses_data": [{"id": w.id, "name": w.name}
                            for w in Warehouse.objects.order_by("-is_default", "name")],
        "items_data": [{"id": i.id, "name": i.name, "unit": i.get_unit_display(),
                        "stock": {str(w): str(q) for w, q in stock.get(i.id, {}).items()}} for i in items],
        "methods": SalePayment.Method.choices,
        "lines_editable": sale is None or sale.status == Sale.Status.REGISTERED,
        "lines": list(sale.lines.select_related("item", "warehouse").order_by("pk")) if sale is not None else [],
    }


@cap_required("sales.create")
def sale_new(request):
    if request.method == "POST":
        try:
            sale = sales_svc.create_sale(
                actor=request.user, lines_raw=_lines_json(request.POST) or [],
                customer_name=request.POST.get("customer_name", ""),
                customer_phone=request.POST.get("customer_phone", ""),
                notes=request.POST.get("notes", ""),
                pay_amount_raw=request.POST.get("pay_amount", ""), pay_method=request.POST.get("pay_method", ""))
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, FORM, _form_context(None, request.POST))
        messages.success(request, f"فروش {sale.number} ثبت شد. اقلام هنوز از انبار کم نشده‌اند؛ بعد از «تحویل» کم می‌شوند.")
        return redirect(DETAIL, sale.id)
    return render(request, FORM, _form_context(None, None))


@cap_required("accounting.access")
def sale_detail(request, sale_id):
    sale = get_object_or_404(sales_svc.sales_queryset(), pk=sale_id)
    payments = list(sale.payments.select_related("created_by"))
    lines = list(sale.lines.select_related("item", "warehouse").order_by("pk"))
    stock = stock_by_warehouse({l.item_id for l in lines})
    need = {}
    for l in lines:
        key = (l.item_id, l.warehouse_id)
        need[key] = need.get(key, Decimal("0")) + l.qty
    registered = sale.status == Sale.Status.REGISTERED
    for l in lines:
        l.stock_now = stock.get(l.item_id, {}).get(l.warehouse_id, Decimal("0"))
        l.short = registered and need[(l.item_id, l.warehouse_id)] > l.stock_now
    return render(request, "finance/accounting_sale.html", {
        "nav_active": "sales", "sale": sale,
        "status_variant": sales_svc.STATUS_VARIANT.get(sale.status, "neutral"),
        "lines": lines, "short_count": sum(1 for l in lines if l.short),
        "payments": payments, "events": list(sale.events.select_related("actor")[:50]),
        "can_cancel": sale.status == Sale.Status.REGISTERED and not payments,
        "methods": SalePayment.Method.choices,
    })


@cap_required("sales.create")
def sale_edit(request, sale_id):
    sale = get_object_or_404(sales_svc.sales_queryset(), pk=sale_id)
    if sale.status == Sale.Status.CANCELLED:
        messages.error(request, "فروش لغوشده قابل ویرایش نیست.")
        return redirect(DETAIL, sale.id)
    if request.method == "POST":
        full = sale.status == Sale.Status.REGISTERED
        try:
            sales_svc.update_sale(
                sale, actor=request.user, customer_name=request.POST.get("customer_name", ""),
                customer_phone=request.POST.get("customer_phone", ""), notes=request.POST.get("notes", ""),
                lines_raw=_lines_json(request.POST) if full else None)
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, FORM, _form_context(sale, request.POST))
        messages.success(request, "تغییرات ذخیره شد.")
        return redirect(DETAIL, sale.id)
    return render(request, FORM, _form_context(sale, None))


@cap_required("sales.create")
@require_POST
def sale_deliver(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sales_svc.deliver_sale(sale, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "تحویل ثبت شد و اقلام از انبار کم شد.")
    return redirect(DETAIL, sale.id)


@cap_required("sales.create")
@require_POST
def sale_cancel(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sales_svc.cancel_sale(sale, actor=request.user, reason=request.POST.get("reason"))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "فروش لغو شد.")
    return redirect(DETAIL, sale.id)


@cap_required("accounting.access")
def sale_pdf(request, sale_id):
    sale = get_object_or_404(sales_svc.sales_queryset(), pk=sale_id)
    if sale.status == Sale.Status.CANCELLED:
        messages.error(request, "فروش لغوشده پیش‌فاکتور ندارد.")
        return redirect(DETAIL, sale.id)
    html = render_to_string("finance/sale_pdf.html", {
        "sale": sale, "lines": list(sale.lines.select_related("item").order_by("pk"))}, request=request)
    pdf = weasyprint.HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    response = FileResponse(io.BytesIO(pdf), as_attachment=True, filename=f"{sale.number}.pdf",
                            content_type="application/pdf")
    response["Cache-Control"] = "private, no-store"
    return response


@cap_required("accounting.access")
@require_POST
def payment_add(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    try:
        sales_svc.add_sale_payment(
            sale, actor=request.user, amount_raw=request.POST.get("amount"), method=request.POST.get("method"),
            paid_date=_parse_date(request.POST.get("paid_date")), reference=request.POST.get("reference_number", ""),
            note=request.POST.get("note", ""))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "پرداخت ثبت شد.")
    return redirect(DETAIL, sale.id)


@cap_required("accounting.access")
@require_POST
def payment_edit(request, payment_id):
    payment = get_object_or_404(SalePayment, pk=payment_id)
    try:
        sales_svc.update_sale_payment(
            payment.pk, actor=request.user, amount_raw=request.POST.get("amount"), method=request.POST.get("method"),
            paid_date=_parse_date(request.POST.get("paid_date")), reference=request.POST.get("reference_number", ""),
            note=request.POST.get("note", ""))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "پرداخت ویرایش شد.")
    return redirect(DETAIL, payment.sale_id)


@cap_required("accounting.access")
@require_POST
def payment_delete(request, payment_id):
    payment = get_object_or_404(SalePayment, pk=payment_id)
    try:
        sales_svc.delete_sale_payment(payment.pk, actor=request.user, reason=request.POST.get("reason"))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "پرداخت حذف شد.")
    return redirect(DETAIL, payment.sale_id)


def _customer_base(sale_id):
    base = get_object_or_404(Sale, pk=sale_id)
    if not base.has_customer:
        raise Http404
    return base


def _customer_ctx(request, base):
    return _sales_ctx(request, qs=sales_svc.customer_sales_qs(base), container_id="table-acc-customer-sales",
                      prefix="cs_", list_url=reverse("finance:accounting_sale_customer_table", args=[base.id]))


@cap_required("accounting.access")
def sale_customer(request, sale_id):
    base = _customer_base(sale_id)
    ctx = _customer_ctx(request, base)
    ctx.update(nav_active="sales", base=base,
               stats=sales_svc.sales_stats(sales_svc.customer_sales_qs(base)))
    return render(request, "finance/accounting_sale_customer.html", ctx)


@cap_required("accounting.access")
def sale_customer_table(request, sale_id):
    return render_table(request, _customer_ctx(request, _customer_base(sale_id)))


@cap_required("sales.create")
@require_POST
def sale_customer_edit(request, sale_id):
    _customer_base(sale_id)
    try:
        n = sales_svc.update_customer(actor=request.user, sale_id=sale_id,
                                      name=request.POST.get("customer_name"),
                                      phone=request.POST.get("customer_phone"))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"مشتری در {n} فروش اصلاح شد.")
    return redirect("finance:accounting_sale_customer", sale_id)
