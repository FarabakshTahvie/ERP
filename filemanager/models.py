from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ManagedFile(TimeStampedModel):
    """فایل مشترک مدیر و حسابدار؛ خودِ فایل در ابر آروان است (کلید key)."""
    name = models.CharField(max_length=255, verbose_name="نام فایل")
    key = models.CharField(max_length=255, unique=True, editable=False, verbose_name="کلید در فضای ابری")
    size = models.PositiveBigIntegerField(verbose_name="حجم (بایت)")
    code = models.CharField(max_length=12, unique=True, editable=False, verbose_name="کد لینک کوتاه")
    is_public = models.BooleanField(default=False, verbose_name="عمومی")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="آپلودکننده")

    class Meta:
        verbose_name = "فایل"
        verbose_name_plural = "فایل‌ها"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name
