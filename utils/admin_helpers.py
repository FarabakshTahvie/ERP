from django.db import models
from unfold.decorators import display
from utils.jalali import jalali_str
from jalali_date.fields import JalaliDateField as PackageJalaliDateField, SplitJalaliDateTimeField
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime


def jalali_column(field_name, label):
    """
    متد صریح برای نمایش تاریخ/زمان شمسی در ستون‌های ادمین (list_display و readonly_fields).
    این فقط نمایش است؛ کاری به ویجت فرم ویرایش ندارد.
    """
    @display(description=label, ordering=field_name)
    def _col(self, obj):
        val = getattr(obj, field_name, None)
        if callable(val):
            val = val()
        return jalali_str(val)
    return _col


class JalaliAdminMixin:
    """
    فیلدهای DateField/DateTimeField قابل‌ویرایش در فرم ادمین با تقویم گرافیکی
    پکیج django-jalali-date نمایش داده می‌شوند (نشست قبل تست و تایید شد).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formfield_overrides = {
            **getattr(self, "formfield_overrides", {}),
            models.DateField: {
                "form_class": PackageJalaliDateField,
                "widget": AdminJalaliDateWidget,
            },
            models.DateTimeField: {
                "form_class": SplitJalaliDateTimeField,
                "widget": AdminSplitJalaliDateTime,
            },
        }
