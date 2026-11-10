import uuid

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


def _new_token():
    return uuid.uuid4().hex


class SavedLocation(TimeStampedModel):
    """موقعیت دلخواه (انبار، دفتر، محل قرار). جدا از core.Location که مال پروژه‌هاست."""
    title = models.CharField(max_length=120, verbose_name="عنوان")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="عرض جغرافیایی")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="طول جغرافیایی")
    image = models.ImageField(upload_to="locations/", blank=True, verbose_name="تصویر")
    token = models.CharField(max_length=32, unique=True, default=_new_token, editable=False,
                             verbose_name="کد لینک عمومی")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="ثبت‌کننده")

    class Meta:
        verbose_name = "موقعیت"
        verbose_name_plural = "موقعیت‌ها"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
