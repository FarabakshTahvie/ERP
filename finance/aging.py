from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from finance.models import Invoice

BUCKET_LABELS = {
    "current": "سررسیدنشده",
    "1-30": "۱ تا ۳۰ روز",
    "31-60": "۳۱ تا ۶۰ روز",
    "61-90": "۶۱ تا ۹۰ روز",
    "over-90": "بیش از ۹۰ روز",
}
_KEYS = {"current": "current", "1-30": "days_1_30", "31-60": "days_31_60",
         "61-90": "days_61_90", "over-90": "days_over_90"}


def debt_invoices(qs=None):
    """فاکتورهای بدهی‌ساز: لغونشده و (مشتری تایید کرده یا پولی رویش پرداخت شده).
    پیش‌فاکتورِ تاییدنشده بدهی حساب نمی‌شود. تنها منبع تعریف «بدهی» در کل سیستم."""
    from projects.models import ProjectStage
    confirmed = Exists(ProjectStage.objects.filter(
        project=OuterRef("project"), step_template__requires_payment_selection=True,
        status=ProjectStage.Status.DONE))
    qs = Invoice.objects.all() if qs is None else qs
    return (qs.exclude(status=Invoice.Status.CANCELLED).annotate(is_confirmed=confirmed)
            .filter(Q(is_confirmed=True) | Q(paid_amount__gt=0)))


def get_customer_aging_data(party, today=None):
    """سن بدهی از سررسید (وگرنه تاریخ صدور). فقط فاکتور بدهی‌ساز با مانده‌ی مثبت."""
    today = today or timezone.localdate()
    invoices = debt_invoices(party.invoices.all()).exclude(status=Invoice.Status.PAID).select_related("project")
    summary = {v: 0 for v in _KEYS.values()}
    rows = []
    for inv in invoices:
        remaining = inv.remaining_amount
        if remaining <= 0:
            continue
        base = inv.due_date or inv.issue_date
        delta = (today - base).days if base else 0
        if delta <= 0:
            bucket = "current"
        elif delta <= 30:
            bucket = "1-30"
        elif delta <= 60:
            bucket = "31-60"
        elif delta <= 90:
            bucket = "61-90"
        else:
            bucket = "over-90"
        summary[_KEYS[bucket]] += remaining
        rows.append({"invoice": inv, "remaining": remaining, "delta_days": delta,
                     "bucket": bucket, "bucket_label": BUCKET_LABELS[bucket]})
    summary["total_outstanding"] = sum(r["remaining"] for r in rows)
    summary["overdue"] = summary["total_outstanding"] - summary["current"]
    return summary, rows
