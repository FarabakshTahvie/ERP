from datetime import timedelta
import io
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, Case, IntegerField, Sum, Value, When
from django.http import Http404, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
import weasyprint

from core.capabilities import can
from utils.generic_table import build_table_context, render_table
from utils.jalali import jalali_str, to_fa_digits
from utils.jalali_forms import JalaliDateField
from utils.utils import separate_digits
from .aging import debt_invoices, get_customer_aging_data
from .models import CHEQUE_ACTIVE, Invoice, Payment
from .services import (
    approve_payment, reject_payment, create_customer_payment, PROOF_METHODS,
    CHEQUE_REASON_REQUIRED, CHEQUE_TRANSITIONS, cheque_due_warning, set_cheque_status, update_cheque_info,
    CHEQUE_SOON_DAYS, cheque_soon_q,
)


def _invoice_access(user, invoice):
    """(مجاز؟، مالک؟) مالک = طرف‌حساب همین فاکتور. مدیر و حسابدار فقط می‌بینند؛ ثبت پرداخت فقط برای مالک."""
    party = getattr(user, "party", None)
    is_owner = bool(party and invoice.billed_party_id == party.id)
    return (is_owner or can(user, "accounting.access")), is_owner


@login_required
def invoice_detail(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    allowed, is_owner = _invoice_access(request.user, invoice)
    if not allowed:
        raise Http404

    from projects.models import StageApproval
    pending_approval = StageApproval.objects.filter(
        stage__project=invoice.project, decision=StageApproval.Decision.PENDING
    ).select_related("stage").first()
    payments = invoice.payments.order_by("-created_at")
    return render(request, "finance/portal_invoice.html", {
        "invoice": invoice, "pending_approval": pending_approval, "payments": payments, "is_owner": is_owner,
    })


@login_required
def invoice_pdf(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    allowed, _is_owner = _invoice_access(request.user, invoice)
    if not allowed:
        raise Http404

    html = render_to_string("finance/invoice_pdf.html", {"invoice": invoice}, request=request)
    pdf_bytes = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    return FileResponse(io.BytesIO(pdf_bytes), as_attachment=False,
                        filename=f"{invoice.number}.pdf", content_type="application/pdf")


@login_required
def add_payment(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    _allowed, is_owner = _invoice_access(request.user, invoice)
    if not is_owner:   # مدیر و حسابدار از مسیر «ثبت پرداخت» پرونده‌ی مالی استفاده می‌کنند
        raise Http404
    if invoice.remaining_amount <= 0:
        messages.info(request, "این فاکتور تسویه شده است.")
        return redirect("finance:portal_invoice_detail", invoice.uuid)

    if request.method == "POST":
        try:
            create_customer_payment(
                invoice=invoice,
                method=request.POST.get("payment_method"),
                amount_raw=request.POST.get("payment_amount"),
                reference_number=request.POST.get("reference_number", ""),
                note=request.POST.get("payment_note", ""),
                receipt_file=request.FILES.get("receipt_file"),
                cheque_number=request.POST.get("cheque_number", ""),
                cheque_bank=request.POST.get("cheque_bank", ""),
            )
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, "finance/portal_add_payment.html", {"invoice": invoice})
        messages.success(request, "پرداخت ثبت شد و پس از بررسی رسید توسط کارشناس تایید می‌شود.")
        return redirect("finance:portal_invoice_detail", invoice.uuid)

    return render(request, "finance/portal_add_payment.html", {"invoice": invoice})


CHEQUE_VARIANT = {"received": "info", "deposited": "info", "collected": "success",
                  "endorsed": "neutral", "bounced": "error", "returned": "neutral"}
CHEQUE_STEP_ORDER = ("deposited", "collected", "endorsed", "bounced", "returned", "received")
 
 
def _parse_jalali(raw):
    """تاریخ شمسی فرم ← date؛ خالی = None؛ نامعتبر = ValueError فارسی."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return JalaliDateField().clean(raw)
    except ValidationError as e:
        raise ValueError(" ".join(e.messages))
 
 
def _cheque_context(payment):
    labels = dict(Payment.ChequeStatus.choices)
    allowed = CHEQUE_TRANSITIONS.get(payment.cheque_status, set())
    return {
        "cheque_variant": CHEQUE_VARIANT.get(payment.cheque_status, "neutral"),
        "cheque_choices": [{"value": s, "label": labels[s], "reason": s in CHEQUE_REASON_REQUIRED}
                           for s in CHEQUE_STEP_ORDER if s in allowed],
        "cheque_warning": (cheque_due_warning(payment.cheque_due_date)
                           if payment.cheque_status in CHEQUE_ACTIVE else ""),
        "cheque_history": [
            {"at": e.created_at,
             "title": "ویرایش اطلاعات" if e.from_status == e.to_status else labels.get(e.to_status, e.to_status),
             "note": e.note,
             "who": (e.actor.get_full_name() or e.actor.username) if e.actor else "سیستم"}
            for e in reversed(list(payment.cheque_events.select_related("actor")))],
    }


def _can_review_payments(user):
    return can(user, "payments.review")


def _visible_payments(user):
    return Payment.objects.select_related("invoice__project", "invoice__billed_party", "approved_by")


def _payments_table_context(request):
    qs = _visible_payments(request.user).annotate(
        review_rank=Case(When(status=Payment.Status.PENDING, then=0), default=1, output_field=IntegerField()),
        cheque_soon=Case(When(cheque_soon_q(), then=Value(True)), default=Value(False), output_field=BooleanField()),
    ).order_by("review_rank", "-created_at")
    today = timezone.localdate()
 
    def cheque_cells(p):
        if not p.cheque_status:
            return [{"type": "muted", "value": "—"}, {"type": "muted", "value": "—"}]
        status_cell = {"type": "badge", "value": p.get_cheque_status_display(),
                       "variant": CHEQUE_VARIANT.get(p.cheque_status, "neutral")}
        if p.cheque_due_date is None:
            return [status_cell, {"type": "muted", "value": "—"}]
        text = jalali_str(p.cheque_due_date, fmt="%Y/%m/%d")
        if p.cheque_soon:
            due_cell = {"type": "badge", "value": text,
                        "variant": "error" if p.cheque_due_date < today else "warning"}
        else:
            due_cell = {"type": "muted", "value": text}
        return [status_cell, due_cell]
 
    def row_builder(p):
        from utils.navigation import nav_reverse
        return {
            "url": nav_reverse(request, "finance:payment_detail", args=[p.id]),
            "cells": [
                {"type": "text", "value": p.invoice.project.name},
                {"type": "muted", "value": to_fa_digits(p.invoice.number)},
                {"type": "badge", "value": p.get_method_display(), "variant": "neutral"},
                {"type": "text", "value": to_fa_digits(separate_digits(p.amount))},
                {"type": "muted", "value": jalali_str(p.created_at, fmt="%Y/%m/%d %H:%M")},
                {"type": "badge", "value": p.status_label, "variant": p.status_variant},
                *cheque_cells(p),
            ],
        }
 
    return build_table_context(
        request, qs,
        columns=[
            {"label": "پروژه", "sort_field": "invoice__project__name"},
            {"label": "فاکتور", "sort_field": "invoice__number"},
            {"label": "روش", "sort_field": "method", "filter_key": "method", "filter_type": "select",
             "choices": Payment.Method.choices},
            {"label": "مبلغ (تومان)", "sort_field": "amount", "filter_key": "amount", "filter_type": "number_range"},
            {"label": "تاریخ ثبت", "sort_field": "created_at"},
            {"label": "وضعیت", "sort_field": "status", "filter_key": "status", "filter_type": "select",
             "choices": Payment.Status.choices},
            {"label": "وضعیت چک", "sort_field": "cheque_status", "filter_key": "cheque", "filter_type": "select",
             "filter_field": "cheque_status", "choices": Payment.ChequeStatus.choices},
            {"label": "سررسید چک", "sort_field": "cheque_due_date", "filter_key": "cheque_soon",
             "filter_type": "boolean", "true_label": f"تا {to_fa_digits(CHEQUE_SOON_DAYS)} روز آینده یا گذشته",
             "false_label": "سایر"},
        ],
        row_builder=row_builder,
        container_id="table-payments",
        param_prefix="py_",
        empty_icon="receipt", empty_text="هنوز پرداختی ثبت نشده.",
        list_url=reverse("finance:payments_table"),
        search_fields=["invoice__project__name", "invoice__number", "invoice__billed_party__name", "reference_number"],
        search_placeholder="جستجو در پروژه، فاکتور، طرف‌حساب یا شماره پیگیری...",
    )


@login_required
@user_passes_test(_can_review_payments)
def payments_review(request):
    context = _payments_table_context(request)
    context["pending_count"] = _visible_payments(request.user).filter(status=Payment.Status.PENDING).count()
    return render(request, "finance/payments_review.html", context)


@login_required
@user_passes_test(_can_review_payments)
def payments_table(request):
    return render_table(request, _payments_table_context(request))


@login_required
@user_passes_test(_can_review_payments)
def payment_detail(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    is_cheque = payment.method == Payment.Method.CHEQUE
    ctx = {
        "payment": payment,
        "invoice": payment.invoice,
        "needs_amount": payment.method in PROOF_METHODS,
        "claimed_amount": payment.claimed_amount if payment.claimed_amount is not None else payment.amount,
        "is_cheque": is_cheque,
        "cheque_due_value": jalali_str(payment.cheque_due_date, fmt="%Y/%m/%d") if payment.cheque_due_date else "",
    }
    if is_cheque and payment.cheque_status:
        ctx.update(_cheque_context(payment))
    return render(request, "finance/payment_detail.html", ctx)


@login_required
@user_passes_test(_can_review_payments)
def payment_decide(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    if request.method != "POST":
        return redirect("finance:payment_detail", payment.id)

    action = request.POST.get("action")
    try:
        if action == "approve":
            extra = {}
            if payment.method == Payment.Method.CHEQUE:
                extra = dict(cheque_number=request.POST.get("cheque_number"),
                             cheque_bank=request.POST.get("cheque_bank"),
                             cheque_due_date=_parse_jalali(request.POST.get("cheque_due_date")))
            approved = approve_payment(payment, approved_by=request.user,
                                       verified_amount=request.POST.get("verified_amount"), **extra)
            messages.success(request, "پرداخت تایید شد.")
            if approved.method == Payment.Method.CHEQUE:
                warning = cheque_due_warning(approved.cheque_due_date)
                if warning:
                    messages.warning(request, warning)
        elif action == "reject":
            reject_payment(payment, rejected_by=request.user, reason=request.POST.get("reason", ""))
            messages.warning(request, "پرداخت رد شد.")
        else:
            messages.error(request, "عملیات نامعتبر است.")
            return redirect("finance:payment_detail", payment.id)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("finance:payment_detail", payment.id)
    return redirect("finance:payments_review")


@login_required
@user_passes_test(_can_review_payments)
@require_POST
def payment_cheque_status(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    try:
        set_cheque_status(payment=payment, status=request.POST.get("status", ""), actor=request.user,
                          endorsed_to=request.POST.get("endorsed_to", ""), note=request.POST.get("note", ""))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "وضعیت چک ثبت شد.")
    return redirect("finance:payment_detail", payment.id)


@login_required
@user_passes_test(_can_review_payments)
@require_POST
def payment_cheque_info(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    try:
        due = _parse_jalali(request.POST.get("due_date"))
        update_cheque_info(payment=payment, number=request.POST.get("number"), bank=request.POST.get("bank"),
                           due_date=due, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "اطلاعات چک ذخیره شد.")
        warning = cheque_due_warning(due)
        if warning:
            messages.warning(request, warning)
    return redirect("finance:payment_detail", payment.id)


@login_required
def statement(request):
    """صورت‌حساب خود طرف‌حساب: فقط از فاکتور و پرداخت؛ اعتباری فقط اطلاع است و مانده را عوض نمی‌کند."""
    party = getattr(request.user, "party", None)
    if party is None:
        raise Http404
    live = party.invoices.exclude(status=Invoice.Status.CANCELLED)
    debts = list(debt_invoices(party.invoices.all()).select_related("project").order_by("-issue_date"))
    waiting = list(live.exclude(pk__in=[i.pk for i in debts]).select_related("project"))
    summary, aging_rows = get_customer_aging_data(party)
    payments = Payment.objects.filter(invoice__in=live).select_related("invoice").order_by("-created_at")[:50]
    pending_total = (Payment.objects.filter(invoice__in=live, status=Payment.Status.PENDING)
                     .exclude(method=Payment.Method.CREDIT).aggregate(t=Sum("amount"))["t"] or 0)
    return render(request, "finance/portal_statement.html", {
        "party": party, "summary": summary, "aging_rows": aging_rows, "debts": debts, "waiting": waiting,
        "payments": payments, "pending_total": pending_total,
        "paid_total": sum((i.paid_amount for i in debts), 0),
    })
