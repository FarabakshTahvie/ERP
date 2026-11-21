import logging
import re

import requests
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from utils.utils import separate_digits
from .deadline import assert_not_expired
from .models import AccountingEvent, GatewayTransaction, Invoice, Payment
from .services import parse_amount

logger = logging.getLogger(__name__)

RIAL_PER_TOMAN = 10          # فاکتورها تومانی‌اند؛ مبلغ به ریال فرستاده و به همان ریال verify می‌شود
MIN_TOMAN = 1000
MAX_TOMAN = 100_000_000      # سقف زرین‌پال (کد -41)
TIMEOUT = 15
SUCCESS_CODES = (100, 101)   # ۱۰۱ یعنی قبلاً verify شده

ERROR_TEXT = {
    -9: "اطلاعات پرداخت از طرف درگاه پذیرفته نشد.",
    -12: "تعداد تلاش‌ها زیاد است؛ چند دقیقه بعد دوباره تلاش کنید.",
    -41: "حداکثر مبلغ پرداخت آنلاین ۱۰۰ میلیون تومان است.",
}
GENERIC_ERROR = "درگاه پرداخت در دسترس نیست؛ کمی بعد دوباره تلاش کنید یا با دفتر تماس بگیرید."
NOT_RECORDED = ("این پرداخت در فاکتور ثبت نشد. اگر مبلغی از حساب شما کسر شده، به‌صورت خودکار برگردانده "
                "می‌شود؛ در صورت تاخیر با دفتر تماس بگیرید.")
UNKNOWN_RESULT = ("نتیجه‌ی پرداخت هنوز از درگاه مشخص نشد. اگر پرداخت در فاکتور ثبت نشد، مبلغ به‌صورت خودکار "
                  "به حساب شما برمی‌گردد؛ برای پیگیری با دفتر تماس بگیرید.")


def gateway_enabled():
    """سندباکس پرداخت جعلی را هم «موفق» می‌کند؛ بدون DEBUG هرگز فعال نمی‌شود."""
    if not (settings.ZARINPAL_ENABLED and settings.ZARINPAL_MERCHANT_ID):
        return False
    if settings.ZARINPAL_SANDBOX and not settings.DEBUG:
        logger.error("ZarinPal sandbox is on while DEBUG is off; gateway disabled")
        return False
    return True


def _base():
    return "https://sandbox.zarinpal.com" if settings.ZARINPAL_SANDBOX else "https://payment.zarinpal.com"


def callback_url():
    return settings.SITE_BASE_URL.rstrip("/") + reverse("finance:gateway_callback")


def _post(path, payload):
    """بدن JSON پاسخ، یا None اگر ارتباط برقرار نشد یا پاسخ JSON نبود."""
    try:
        response = requests.post(f"{_base()}/pg/v4/payment/{path}.json", json=payload,
                                 headers={"Accept": "application/json"}, timeout=TIMEOUT)
        body = response.json()
    except (requests.exceptions.RequestException, ValueError):
        logger.error("zarinpal %s: request failed", path)
        return None
    return body if isinstance(body, dict) else None


def _result(body):
    """(کد، data). موفق: data.code؛ خطا: errors.code (در موفقیت errors لیست خالی است)."""
    data = body.get("data") if isinstance(body.get("data"), dict) else {}
    errors = body.get("errors") if isinstance(body.get("errors"), dict) else {}
    return (data.get("code") if data else errors.get("code")), data


def start_payment(*, invoice, user, amount_raw=""):
    """درخواست پرداخت می‌سازد و آدرس صفحه‌ی زرین‌پال را برمی‌گرداند. هر ایرادی ValueError فارسی."""
    if not gateway_enabled():
        raise ValueError("پرداخت آنلاین فعال نیست.")
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("این فاکتور لغو شده است و پرداخت جدید ثبت نمی‌شود.")
    assert_not_expired(invoice)
    remaining = invoice.remaining_amount
    if remaining <= 0:
        raise ValueError("این فاکتور مانده‌ای برای پرداخت ندارد.")
    amount = parse_amount(amount_raw) if str(amount_raw or "").strip() else remaining
    if amount > remaining:
        raise ValueError(f"مبلغ نمی‌تواند از مانده‌ی فاکتور ({separate_digits(remaining)} تومان) بیشتر باشد.")
    if amount < MIN_TOMAN:
        raise ValueError(f"حداقل مبلغ پرداخت آنلاین {separate_digits(MIN_TOMAN)} تومان است.")
    if amount > MAX_TOMAN:
        raise ValueError("حداکثر مبلغ پرداخت آنلاین ۱۰۰ میلیون تومان است.")

    metadata = {"order_id": invoice.number, "auto_verify": False}   # verify را خودمان می‌زنیم؛ نزنیم ← پول برمی‌گردد
    phone = getattr(user, "phone_number", None)
    if phone and re.fullmatch(r"09\d{9}", phone):
        metadata["mobile"] = phone
    body = _post("request", {
        "merchant_id": settings.ZARINPAL_MERCHANT_ID,
        "amount": int(amount) * RIAL_PER_TOMAN,
        "callback_url": callback_url(),
        "description": f"پرداخت فاکتور {invoice.number}",
        "metadata": metadata,
    })
    if body is None:
        raise ValueError("ارتباط با درگاه برقرار نشد؛ دوباره تلاش کنید.")
    code, data = _result(body)
    authority = data.get("authority")
    if code != 100 or not authority:
        logger.error("zarinpal request rejected: code=%s", code)
        raise ValueError(ERROR_TEXT.get(code, GENERIC_ERROR) + (f" (کد خطا: {code})" if code is not None else ""))
    GatewayTransaction.objects.create(
        invoice=invoice, user=user if getattr(user, "pk", None) else None, amount=amount, authority=authority)
    return f"{_base()}/pg/StartPay/{authority}"


def _approve_waiting_stage(invoice, user):
    """پرداخت آنلاین یعنی تایید همان مرحله‌ی «تایید پیش‌فاکتور و پرداخت». شکست این کار نباید پرداخت را برگرداند."""
    from projects.models import StageApproval
    from projects.services import decide_stage_approval
    try:
        with transaction.atomic():
            approval = (StageApproval.objects.select_for_update(of=("self",))
                        .filter(stage__project_id=invoice.project_id,
                                stage__step_template__requires_payment_selection=True,
                                decision=StageApproval.Decision.PENDING).first())
            if approval is not None:
                decide_stage_approval(approval, actor=user, decision=StageApproval.Decision.APPROVED,
                                      comment="تایید همراه با پرداخت آنلاین")
    except Exception:
        logger.exception("gateway: stage approval failed for invoice %s", invoice.pk)


def _notify_staff_paid(invoice, payment, ref):
    """به مدیر و حسابدار خبر می‌دهد پولی از درگاه آمده. شکست اعلان نباید پرداخت تاییدشده را برگرداند."""
    from notifications.models import NotificationType
    from notifications.services import notify_staff
    try:
        with transaction.atomic():   # savepoint؛ خطای اعلان تراکنش اصلی را نمی‌شکند
            notify_staff(
                "payments.review", notification_type=NotificationType.GATEWAY_PAYMENT,
                title="پرداخت آنلاین دریافت شد",
                body=(f"{invoice.billed_party.name} برای پروژه «{invoice.project.name}» مبلغ "
                      f"{separate_digits(payment.amount)} تومان از درگاه پرداخت کرد "
                      f"(فاکتور {invoice.number}، پیگیری {ref or '—'}). "
                      f"مانده‌ی فاکتور: {separate_digits(invoice.remaining_amount)} تومان."),
                real_target_url=reverse("finance:payment_detail", args=[payment.pk]),
                extra_data={"invoice_number": invoice.number, "payment_id": payment.pk})
    except Exception:
        logger.exception("gateway: staff notification failed for payment %s", payment.pk)


def finish_payment(*, authority, status):
    """برگشت از درگاه. خروجی: (تراکنش یا None، متن پیام، سطح پیام). تکرار امن (idempotent) است."""
    from .accounting import log_event
    with transaction.atomic():
        tx = (GatewayTransaction.objects.select_for_update(of=("self",)).filter(authority=authority).first())
        if tx is None:
            return None, "", ""
        if tx.status == GatewayTransaction.Status.PAID:
            return tx, "این پرداخت قبلاً در فاکتور ثبت شده است.", "info"
        if tx.status == GatewayTransaction.Status.FAILED:
            return tx, NOT_RECORDED, "error"
        if (status or "").upper() != "OK":
            return tx, ("پرداخت انجام نشد یا لغو شد. اگر مبلغی از حساب شما کسر شده، "
                        "به‌صورت خودکار برگردانده می‌شود."), "warning"

        invoice = Invoice.objects.select_for_update(of=("self",)).get(pk=tx.invoice_id)
        if invoice.status == Invoice.Status.CANCELLED or tx.amount > invoice.remaining_amount:
            tx.status = GatewayTransaction.Status.FAILED   # verify نمی‌زنیم؛ زرین‌پال پول را برمی‌گرداند
            tx.save()
            return tx, NOT_RECORDED, "error"

        body = _post("verify", {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": int(tx.amount) * RIAL_PER_TOMAN,   # همیشه مبلغ ذخیره‌شده؛ هرگز از آدرس برگشت
            "authority": tx.authority,
        })
        if body is None:
            return tx, UNKNOWN_RESULT, "warning"          # pending می‌ماند؛ برگشت دوباره از درگاه امن است
        code, data = _result(body)
        if code not in SUCCESS_CODES:
            tx.status, tx.result_code = GatewayTransaction.Status.FAILED, code if isinstance(code, int) else None
            tx.save()
            return tx, NOT_RECORDED, "error"

        now = timezone.now()
        ref = str(data.get("ref_id") or "")
        pan = str(data.get("card_pan") or "")
        payment = Payment.objects.create(
            invoice=invoice, method=Payment.Method.GATEWAY, amount=tx.amount, claimed_amount=tx.amount,
            status=Payment.Status.APPROVED, approved_at=now, paid_at=now, reference_number=ref,
            note=f"درگاه زرین‌پال" + (f" — کارت {pan}" if pan else ""))
        tx.status, tx.ref_id, tx.card_pan = GatewayTransaction.Status.PAID, ref, pan
        tx.result_code, tx.verified_at, tx.payment = code, now, payment
        tx.save()
        log_event(kind=AccountingEvent.Kind.PAYMENT, project=invoice.project, actor=None, amount=tx.amount,
                  text=f"پرداخت آنلاین زرین‌پال ثبت شد (پیگیری {ref or '—'})")
        _approve_waiting_stage(invoice, tx.user)
        _notify_staff_paid(invoice, payment, ref)
        return tx, f"پرداخت با موفقیت انجام شد. شماره‌ی پیگیری: {ref}" if ref else "پرداخت با موفقیت انجام شد.", "success"
