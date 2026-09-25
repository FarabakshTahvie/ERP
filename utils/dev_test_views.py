import json
import jdatetime
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils import timezone

from jalali_date.fields import JalaliDateField as PackageJalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


class PackageCalendarTestForm(forms.Form):
    date_b = PackageJalaliDateField(
        label="گزینه B: پکیج django-jalali-date",
        widget=AdminJalaliDateWidget,
    )


def _is_leap_jalali_year_via_jdatetime(jy):
    """
    روش مطمئن: اگر بشه ۳۰ اسفند همون سال رو ساخت، سال کبیسه است.
    از همون jdatetime که در کل پروژه استفاده می‌کنیم، نه فرمول دستی.
    """
    try:
        jdatetime.date(jy, 12, 30)
        return True
    except ValueError:
        return False


@user_passes_test(_is_superuser)
def dev_test_calendar(request):
    today_j = jdatetime.date.fromgregorian(date=timezone.localdate())
    sample_years = [today_j.year, today_j.year + 1, today_j.year + 2, today_j.year + 3, today_j.year + 5]
    leap_check = [
        {"year": jy, "is_leap": _is_leap_jalali_year_via_jdatetime(jy)}
        for jy in sample_years
    ]
    context = {
        "today_year": today_j.year,
        "today_month": today_j.month,
        "today_day": today_j.day,
        "leap_check": leap_check,
        "form_b": PackageCalendarTestForm(),
    }
    return render(request, "utils/dev_test_calendar.html", context)


@user_passes_test(_is_superuser)
def dev_test_map(request):
    context = {"neshan_key": getattr(settings, "NESHAN_API_KEY", "")}
    return render(request, "utils/dev_test_map.html", context)


@user_passes_test(_is_superuser)
def dev_test_design_system(request):
    return render(request, "utils/dev_test_design_system.html")

