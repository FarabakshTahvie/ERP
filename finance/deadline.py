from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.capabilities import can

DEFAULT_DAYS = 1
MAX_DAYS = 30
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_deadline_days(raw):
    """خالی یا None = پیش‌فرض (۱ روز). غیر از عدد صحیح ۱ تا ۳۰ = ValueError فارسی."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    if not text:
        return DEFAULT_DAYS
    if not text.isdigit() or not (1 <= int(text) <= MAX_DAYS):
        raise ValueError("مهلت تایید باید عددی صحیح بین ۱ تا ۳۰ روز باشد.")
    return int(text)


def last_day_for(days, today=None):
    """آخرین روز تایید = امروز + days. مهلت تا ساعت ۲۴ همان روز است، نه ۲۴ ساعت بعد از صدور."""
    return (today or timezone.localdate()) + timedelta(days=days)


def deadline_open(invoice):
    """مهلت فقط وقتی معنی دارد که مشتری هنوز تایید نکرده و پولی ثبت نشده (همان شرط باز بودن قیمت‌ها)."""
    from projects.services import project_prices_editable
    from .models import Invoice
    if invoice.status == Invoice.Status.CANCELLED or invoice.document_type != Invoice.DocumentType.PROFORMA:
        return False
    return project_prices_editable(invoice.project)


def deadline_state(invoice, today=None):
    """'none' | 'active' | 'expired'"""
    if invoice.valid_until is None or not deadline_open(invoice):
        return "none"
    return "expired" if (today or timezone.localdate()) > invoice.valid_until else "active"


def office_phone_text():
    return settings.COMPANY_CONTACT["office_phone"]["display"]


def expired_message(invoice, today=None):
    if deadline_state(invoice, today) != "expired":
        return ""
    return ("مهلت تایید این پیش‌فاکتور تمام شده است. برای تایید و به‌روزشدن قیمت‌ها با دفتر تماس بگیرید: "
            + office_phone_text())


def assert_not_expired(invoice):
    message = expired_message(invoice)
    if message:
        raise ValueError(message)


@transaction.atomic
def extend_deadline(*, invoice, days_raw, reason, actor):
    """تمدید مهلت (= خروج از تعلیق). فقط مدیر یا حسابدار؛ دلیل اجباری؛ ردپا در AccountingEvent."""
    from utils.jalali import jalali_str
    from .accounting import log_event
    from .models import AccountingEvent, Invoice
    if not can(actor, "pricing.edit"):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند مهلت را تمدید کند.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("دلیل تمدید را بنویسید.")
    days = parse_deadline_days(days_raw)
    invoice = Invoice.objects.select_for_update(of=("self",)).select_related("project").get(pk=invoice.pk)
    if not deadline_open(invoice):
        raise ValueError("این پیش‌فاکتور مهلت ندارد؛ یا مشتری تایید کرده، یا پولی ثبت شده، یا لغو شده است.")
    old, new = invoice.valid_until, last_day_for(days)
    invoice.valid_until = new
    invoice.save(update_fields=["valid_until", "updated_at"])
    show = lambda d: jalali_str(d, fmt="%Y/%m/%d") if d else "ندارد"
    log_event(kind=AccountingEvent.Kind.INVOICE_LINE, project=invoice.project, actor=actor,
              text=f"مهلت تایید پیش‌فاکتور {invoice.number}: {show(old)} ← {show(new)} — {reason}")
    return invoice


def deadline_info(invoice, today=None):
    """برای نمایش در قالب‌ها؛ مشتری و حسابدار هر دو از همین می‌خوانند."""
    today = today or timezone.localdate()
    state = deadline_state(invoice, today)
    return {
        "state": state,
        "last_day": invoice.valid_until if state != "none" else None,
        "days_left": (invoice.valid_until - today).days if state == "active" else None,
        "phone": office_phone_text(),
        "phone_tel": settings.COMPANY_CONTACT["office_phone"]["tel"],
    }


def suspended_invoices_qs(today=None):
    """پیش‌فاکتورهای معلق (مهلت تایید گذشته) یک‌جا روی دیتابیس. همان تعریف deadline_state == "expired" است؛
    شرط‌ها آینه‌ی project_prices_editable‌اند و تست هویت این دو را با هم می‌سنجد."""
    from django.db.models import Exists, OuterRef
    from projects.models import ProjectStage
    from projects.services import EDITABLE_PROJECT_STATUSES
    from .models import Invoice, Payment
    today = today or timezone.localdate()
    confirmed = Exists(ProjectStage.objects.filter(
        project=OuterRef("project"), step_template__requires_payment_selection=True,
        status=ProjectStage.Status.DONE))
    has_payment = Exists(Payment.objects.filter(invoice=OuterRef("pk")).exclude(status=Payment.Status.REJECTED))
    return (Invoice.objects
            .filter(document_type=Invoice.DocumentType.PROFORMA, valid_until__lt=today,
                    project__status__in=EDITABLE_PROJECT_STATUSES)
            .exclude(status=Invoice.Status.CANCELLED)
            .annotate(is_confirmed=confirmed, has_payment=has_payment)
            .filter(is_confirmed=False, has_payment=False))


def notify_expired_proformas(today=None):
    """به مشتریِ هر پیش‌فاکتور معلق پیامک مهلت می‌فرستد (یک‌بار برای هر آخرین روز). خروجی: تعداد صف‌شده."""
    from .services import notify_proforma_expired
    today = today or timezone.localdate()
    invoices = list(suspended_invoices_qs(today).select_related("billed_party", "project"))
    return sum(1 for inv in invoices if notify_proforma_expired(inv))
