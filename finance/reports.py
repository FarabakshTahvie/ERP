import jdatetime
from datetime import datetime, time
from decimal import Decimal
from django.db import models
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
    """
    تولید ساختار داده گزارش مالی دوره‌ای.
    بدون کلمات سود و زیان یا رنگ‌بندی‌های جهت‌دار.
    مبالغ بر اساس فیلترهای فنی نمایش داده می‌شوند.
    """
    # ۱. درآمد ناخالص (فاکتورهای قطعی تاییدشده صادر شده در بازه)
    invoices = Invoice.objects.filter(
        document_type=Invoice.DocumentType.FINAL,
        issue_date__gte=start_g,
        issue_date__lte=end_g
    ).exclude(status=Invoice.Status.CANCELLED)
    
    total_revenue = sum(inv.total_amount for inv in invoices)

    # ۲. هزینه‌ها (شامل خرید مواد و هزینه‌های عملیاتی ثبت‌شده در بازه)
    # خرید مواد:
    purchases_sum = PurchaseLine.objects.filter(
        purchase__purchased_at__date__gte=start_g,
        purchase__purchased_at__date__lte=end_g
    ).aggregate(t=Sum(models.F("qty") * models.F("unit_cost")))["t"] or Decimal("0")

    # هزینه‌های عملیاتی پروژه‌ها:
    operational_costs_sum = ProjectCost.objects.filter(
        created_at__gte=timezone.make_aware(datetime.combine(start_g, time.min)),
        created_at__lte=timezone.make_aware(datetime.combine(end_g, time.max))
    ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    total_expenses = purchases_sum + operational_costs_sum

    # ۳. خالص دریافتی‌ها (پرداخت‌های تاییدشده در بازه)
    total_received = Payment.objects.filter(
        status=Payment.Status.APPROVED,
        paid_at__date__gte=start_g,
        paid_at__date__lte=end_g
    ).exclude(method=Payment.Method.CREDIT).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    # تفاضل نهایی (بدون رنگ‌بندی جهت‌دار یا نام سود و زیان)
    net_difference = total_revenue - total_expenses

    return {
        "start_g": start_g,
        "end_g": end_g,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "total_received": total_received,
        "net_difference": net_difference,
        "purchases_sum": purchases_sum,
        "operational_costs_sum": operational_costs_sum,
    }
