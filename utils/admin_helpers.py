from django.db import models
from unfold.decorators import display
from unfold.widgets import UnfoldAdminTextInputWidget
from utils.jalali import jalali_str
from utils.jalali_forms import JalaliDateField, JalaliDateTimeField


def jalali_column(field_name, label):
    """
    متد صریح برای نمایش تاریخ/زمان شمسی در ستون‌های ادمین (list_display و readonly_fields)
    """
    @display(description=label, ordering=field_name)
    def _col(self, obj):
        val = getattr(obj, field_name, None)
        if callable(val):
            val = val()
        return jalali_str(val)
    return _col


class JalaliAdminMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formfield_overrides = {
            **getattr(self, "formfield_overrides", {}),
            models.DateField: {
                "form_class": JalaliDateField,
                "widget": UnfoldAdminTextInputWidget(attrs={"dir": "ltr", "placeholder": "۱۴۰۵/۰۶/۳۰"}),
            },
            models.DateTimeField: {
                "form_class": JalaliDateTimeField,
                "widget": UnfoldAdminTextInputWidget(attrs={"dir": "ltr", "placeholder": "۱۴۰۵/۰۶/۳۰ ۱۴:۳۰"}),
            },
        }
