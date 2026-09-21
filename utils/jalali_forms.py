import re
from datetime import datetime, date
import jdatetime
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from utils.jalali import jalali_str

_FA_AR_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_digits_and_separators(val_str):
    if not val_str:
        return ""
    val_str = str(val_str).strip().translate(_FA_AR_TO_EN)
    val_str = val_str.replace("-", "/")
    return val_str


class JalaliDateField(forms.Field):
    default_error_messages = {
        "invalid": "تاریخ وارد شده نامعتبر است. نمونه صحیح: ۱۴۰۵/۰۶/۳۰",
    }

    def prepare_value(self, value):
        if isinstance(value, (datetime, date)):
            return jalali_str(value, fmt="%Y/%m/%d", persian=True)
        return value or ""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        val_str = normalize_digits_and_separators(value)
        parts = val_str.split("/")
        if len(parts) != 3:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            jdate = jdatetime.date(year, month, day)
            return jdate.togregorian()
        except (ValueError, TypeError, OverflowError):
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        try:
            data_val = self.to_python(data)
        except ValidationError:
            return True
        initial_val = self.to_python(initial)
        return initial_val != data_val


class JalaliDateTimeField(forms.Field):
    default_error_messages = {
        "invalid": "تاریخ و ساعت وارد شده نامعتبر است. نمونه صحیح: ۱۴۰۵/۰۶/۳۰ ۱۴:۳۰",
    }

    def prepare_value(self, value):
        if isinstance(value, datetime):
            return jalali_str(value, fmt="%Y/%m/%d %H:%M", persian=True)
        elif isinstance(value, date):
            return jalali_str(value, fmt="%Y/%m/%d", persian=True)
        return value or ""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime):
            if timezone.is_naive(value):
                return timezone.make_aware(value)
            return value

        val_str = normalize_digits_and_separators(value)
        tokens = val_str.split()
        if len(tokens) == 1:
            date_part = tokens[0]
            time_part = "00:00:00"
        elif len(tokens) == 2:
            date_part, time_part = tokens[0], tokens[1]
        else:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

        date_parts = date_part.split("/")
        if len(date_parts) != 3:
            raise ValidationError(self.error_messages["invalid"], code="invalid")

        time_parts = time_part.split(":")
        if len(time_parts) not in (2, 3):
            raise ValidationError(self.error_messages["invalid"], code="invalid")

        try:
            year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) == 3 else 0

            jdt = jdatetime.datetime(year, month, day, hour, minute, second)
            greg_dt = jdt.togregorian()
            # Asia/Tehran aware
            tehran_tz = timezone.get_current_timezone()
            aware_dt = timezone.make_aware(greg_dt, timezone=tehran_tz)
            return aware_dt
        except (ValueError, TypeError, OverflowError):
            raise ValidationError(self.error_messages["invalid"], code="invalid")

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        try:
            data_val = self.to_python(data)
        except ValidationError:
            return True
        initial_val = self.to_python(initial)
        if initial_val is None and data_val is None:
            return False
        if initial_val is None or data_val is None:
            return True
        # Compare within minute resolution
        return abs((initial_val - data_val).total_seconds()) > 59
