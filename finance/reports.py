import jdatetime
from datetime import datetime, time
from decimal import Decimal
from django.db import models
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import Sum, Q
from catalog.models import Item
from inventory.models import StockMovement, PurchaseLine
from projects.models import Project, ProjectCost
from finance.models import Payment, Invoice

def get_jalali_date_range(start_date, end_date):
    """
    دریافت بازه تاریخ میلادی بر اساس تاریخ‌های شمسی ورودی به صورت رشته (مثلاً 1405/01/01).
    """
    if not start_date or not end_date:
        return None, None
    try:
        s_y, s_m, s_d = map(int, start_date.split("/"))
        e_y, e_m, e_d = map(int, end_date.split("/"))
        start_g = jdatetime.date(s_y, s_m, s_d).togregorian()
        end_g = jdatetime.date(e_y, e_m, e_d).togregorian()
        if start_g > end_g:
            raise ValueError("تاریخ پایان قبل از تاریخ شروع است.")
        return start_g, end_g
    except Exception as e:
        raise ValueError("فرمت تاریخ‌های ورودی نامعتبر است یا تاریخ پایان قبل از شروع است.")


def generate_periodic_financial_report(start_g, end_g):
    """فقط اعداد؛ بدون برچسب سود/زیان. فروش = همه‌ی فاکتورهای غیرلغوشده با تاریخ صدور در بازه؛
    دریافتی = پرداخت تاییدشده‌ی غیراعتباری با تاریخ مؤثر Coalesce(paid_at, approved_at, created_at)."""
    start_dt = timezone.make_aware(datetime.combine(start_g, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_g, time.max))

    total_revenue = (Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
                     .filter(issue_date__gte=start_g, issue_date__lte=end_g)
                     .aggregate(t=Sum("total_amount"))["t"] or Decimal("0"))

    purchases_sum = PurchaseLine.objects.filter(
        purchase__purchased_at__date__gte=start_g, purchase__purchased_at__date__lte=end_g,
    ).aggregate(t=Sum(models.F("qty") * models.F("unit_cost")))["t"] or Decimal("0")

    operational_costs_sum = ProjectCost.objects.filter(
        created_at__gte=start_dt, created_at__lte=end_dt,
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    total_received = (Payment.objects.filter(status=Payment.Status.APPROVED)
                      .exclude(method=Payment.Method.CREDIT)
                      .annotate(eff_at=Coalesce("paid_at", "approved_at", "created_at"))
                      .filter(eff_at__gte=start_dt, eff_at__lte=end_dt)
                      .aggregate(t=Sum("amount"))["t"] or Decimal("0"))

    total_expenses = purchases_sum + operational_costs_sum
    return {
        "start_g": start_g, "end_g": end_g,
        "total_revenue": total_revenue, "total_expenses": total_expenses,
        "total_received": total_received, "net_difference": total_revenue - total_expenses,
        "purchases_sum": purchases_sum, "operational_costs_sum": operational_costs_sum,
    }
