import io
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Case, IntegerField, When
from django.http import Http404, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
import weasyprint

from utils.generic_table import build_table_context
from utils.jalali import jalali_str, to_fa_digits
from utils.utils import separate_digits
from .models import Invoice, Payment
from .services import approve_payment, reject_payment, create_customer_payment, PROOF_METHODS


@login_required
def invoice_detail(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or invoice.billed_party_id != party.id):
        raise Http404

    from projects.models import StageApproval
    pending_approval = StageApproval.objects.filter(
        stage__project=invoice.project, decision=StageApproval.Decision.PENDING
    ).select_related("stage").first()
    payments = invoice.payments.order_by("-created_at")
    return render(request, "finance/portal_invoice.html", {
        "invoice": invoice, "pending_approval": pending_approval, "payments": payments,
    })


@login_required
def invoice_pdf(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or invoice.billed_party_id != party.id):
        raise Http404

    html = render_to_string("finance/invoice_pdf.html", {"invoice": invoice}, request=request)
    pdf_bytes = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

    return FileResponse(
        io.BytesIO(pdf_bytes),
        as_attachment=False,
        filename=f"{invoice.number}.pdf",
        content_type="application/pdf"
    )


@login_required
def add_payment(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or invoice.billed_party_id != party.id):
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


def _can_review_payments(user):
    from accounts.models import User
    return user.is_authenticated and (user.is_superuser or getattr(user, "role", None) in (User.Role.ADMIN, User.Role.EMPLOYEE))


def _is_payment_manager(user):
    from accounts.models import User
    return user.is_superuser or getattr(user, "role", None) == User.Role.ADMIN


def _visible_payments(user):
    """مدیر همه را می‌بیند؛ تکنسین فقط پرداخت‌های پروژه‌هایی که خودش ثبت کرده."""
    qs = Payment.objects.select_related("invoice__project", "invoice__billed_party", "approved_by")
    if not _is_payment_manager(user):
        qs = qs.filter(invoice__project__created_by=user)
    return qs


PAYMENT_STATUS_VARIANT = {
    Payment.Status.PENDING: "warning",
    Payment.Status.APPROVED: "success",
    Payment.Status.REJECTED: "error",
}


def _payments_table_context(request):
    qs = _visible_payments(request.user).annotate(
        review_rank=Case(When(status=Payment.Status.PENDING, then=0), default=1, output_field=IntegerField()),
    ).order_by("review_rank", "-created_at")

    def row_builder(p):
        return {
            "url": reverse("finance:payment_detail", args=[p.id]),
            "cells": [
                {"type": "text", "value": p.invoice.project.name},
                {"type": "muted", "value": to_fa_digits(p.invoice.number)},
                {"type": "badge", "value": p.get_method_display(), "variant": "neutral"},
                {"type": "text", "value": to_fa_digits(separate_digits(p.amount))},
                {"type": "muted", "value": jalali_str(p.created_at, fmt="%Y/%m/%d %H:%M")},
                {"type": "badge", "value": p.get_status_display(),
                 "variant": PAYMENT_STATUS_VARIANT.get(p.status, "neutral")},
            ],
        }

    return build_table_context(
        request, qs,
        columns=[{"label": "پروژه"}, {"label": "فاکتور"}, {"label": "روش"},
                 {"label": "مبلغ (تومان)"}, {"label": "تاریخ ثبت"}, {"label": "وضعیت"}],
        row_builder=row_builder,
        container_id="table-payments",
        param_prefix="py_",
        empty_icon="receipt", empty_text="هنوز پرداختی ثبت نشده.",
        list_url=reverse("finance:payments_table"),
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
    return render(request, "utils/partials/generic_table.html", _payments_table_context(request))


@login_required
@user_passes_test(_can_review_payments)
def payment_detail(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    return render(request, "finance/payment_detail.html", {
        "payment": payment,
        "invoice": payment.invoice,
        "needs_amount": payment.method in PROOF_METHODS,
        "claimed_amount": payment.claimed_amount if payment.claimed_amount is not None else payment.amount,
    })


@login_required
@user_passes_test(_can_review_payments)
def payment_decide(request, payment_id):
    payment = get_object_or_404(_visible_payments(request.user), pk=payment_id)
    if request.method != "POST":
        return redirect("finance:payment_detail", payment.id)

    action = request.POST.get("action")
    try:
        if action == "approve":
            approve_payment(payment, approved_by=request.user, verified_amount=request.POST.get("verified_amount"))
            messages.success(request, "پرداخت تایید شد.")
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
