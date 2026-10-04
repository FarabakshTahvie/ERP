from datetime import date, datetime
import jdatetime
from django.utils import timezone
from .models import PeriodLock

MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
               "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def jalali_ym(value):
    if isinstance(value, datetime):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    j = jdatetime.date.fromgregorian(date=value)
    return j.year, j.month


def month_label(year, month):
    return f"{MONTH_NAMES[month - 1]} {str(year).translate(_FA)}"


def current_ym():
    return jalali_ym(timezone.localdate())


def is_locked(value):
    if value is None:
        return False
    y, m = jalali_ym(value)
    return PeriodLock.objects.filter(year=y, month=m, is_locked=True).exists()


def assert_open(value, what="این سند"):
    """ValueError فارسی اگر تاریخ داخل ماه بسته باشد."""
    if is_locked(value):
        raise ValueError(f"ماه {month_label(*jalali_ym(value))} بسته شده است؛ {what} با تاریخ داخل این ماه ثبت یا تغییر نمی‌شود.")


def set_lock(year, month, *, locked, user):
    """فقط ماه‌های گذشته بسته می‌شوند (ماه جاری و آینده نه)."""
    if not (1 <= month <= 12):
        raise ValueError("ماه نامعتبر است.")
    if locked and (year, month) >= current_ym():
        raise ValueError("فقط ماه‌های گذشته را می‌توان بست.")
    obj, _ = PeriodLock.objects.get_or_create(year=year, month=month)
    if obj.is_locked == locked:
        raise ValueError("وضعیت این ماه همین است.")
    obj.is_locked, obj.changed_by = locked, user
    obj.save()
    return obj
