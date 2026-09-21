import jdatetime
from datetime import datetime, date
from django.utils import timezone

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def to_fa_digits(value):
    if value is None:
        return ""
    return str(value).translate(_FA)


def jalali_str(value, fmt=None, persian=True):
    if not value:
        return ""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)  # Asia/Tehran
        out = jdatetime.datetime.fromgregorian(datetime=value).strftime(fmt or "%Y/%m/%d %H:%M")
    elif isinstance(value, date):
        out = jdatetime.date.fromgregorian(date=value).strftime(fmt or "%Y/%m/%d")
    else:
        return str(value)
    return to_fa_digits(out) if persian else out
