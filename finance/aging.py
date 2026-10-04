from django.utils import timezone
from finance.models import Invoice

def get_customer_aging_data(party, today=None):
    """
    محاسبه جدول سن بدهی (Aging) برای یک مشتری (Party) بر اساس فاکتورهای تسویه‌نشده.
    دسته‌بندی بازه‌ها بر اساس روزهای گذشت‌شده از سررسید (due_date) یا تاریخ صدور (issue_date):
    - جاری (سررسیدنشده)
    - ۱ تا ۳۰ روز از سررسید گذشته
    - ۳۱ تا ۶۰ روز از سررسید گذشته
    - ۶۱ تا ۹۰ روز از سررسید گذشته
    - بیش از ۹۰ روز از سررسید گذشته
    """
    if today is None:
        today = timezone.localdate()

    invoices = party.invoices.exclude(status__in=[Invoice.Status.CANCELLED, Invoice.Status.PAID])
    
    current = 0
    days_1_30 = 0
    days_31_60 = 0
    days_61_90 = 0
    days_over_90 = 0

    aging_rows = []

    for inv in invoices:
        remaining = inv.remaining_amount
        if remaining <= 0:
            continue
        
        base_date = inv.due_date or inv.issue_date
        delta_days = (today - base_date).days if base_date else 0

        bucket = "current"
        if delta_days <= 0:
            current += remaining
        elif 1 <= delta_days <= 30:
            days_1_30 += remaining
            bucket = "1-30"
        elif 31 <= delta_days <= 60:
            days_31_60 += remaining
            bucket = "31-60"
        elif 61 <= delta_days <= 90:
            days_61_90 += remaining
            bucket = "61-90"
        else:
            days_over_90 += remaining
            bucket = "over-90"

        aging_rows.append({
            "invoice": inv,
            "remaining": remaining,
            "delta_days": delta_days,
            "bucket": bucket,
        })

    summary = {
        "current": current,
        "days_1_30": days_1_30,
        "days_31_60": days_31_60,
        "days_61_90": days_61_90,
        "days_over_90": days_over_90,
        "total_outstanding": party.total_outstanding,
    }

    return summary, aging_rows
