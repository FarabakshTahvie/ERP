from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created_at and updated_at fields.
    """
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ثبت"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="تاریخ بروزرسانی"
    )

    class Meta:
        abstract = True


class DeviceType(models.TextChoices):
    WEB = 'web', 'وب (Web)'
    ANDROID = 'android', 'اندروید (Android)'
    IOS = 'ios', 'آی او اس (iOS)'


class PushDeviceQuerySet(models.QuerySet):
    """
    Custom QuerySet for bulk messaging to devices (fcm-django pattern).
    """

    def active(self):
        return self.filter(is_active=True)

    def send_message(self, title, body, url=None, icon=None, data=None):
        from utils.push_notification import NajvaService
        tokens = list(self.active().values_list('registration_id', flat=True))
        if not tokens:
            return {"success": False, "error": "No active device tokens found"}
        result = NajvaService().send(title=title, body=body, subscriber_tokens=tokens, url=url)
        invalid = result.get("invalid_tokens") or []
        if invalid:
            self.model.objects.filter(registration_id__in=invalid).update(is_active=False)
        return result


class PushDevice(TimeStampedModel):
    """
    Professional Device Token model inspired by fcm_django.
    Stores device tokens, browser, OS, and handles user device associations.
    Inherits created_at and updated_at from TimeStampedModel.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='push_devices',
        verbose_name="کاربر"
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="نام دستگاه"
    )
    registration_id = models.TextField(
        unique=True,
        verbose_name="شناسه توکن دستگاه (Push Token)"
    )
    device_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="شناسه یکتای دستگاه"
    )
    type = models.CharField(
        max_length=10,
        choices=DeviceType.choices,
        default=DeviceType.WEB,
        verbose_name="نوع دستگاه"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="وضعیت فعال بودن"
    )
    browser = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="مرورگر"
    )
    os = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="سیستم عامل"
    )

    objects = PushDeviceQuerySet.as_manager()

    class Meta:
        verbose_name = "دستگاه پوش نوتیفیکیشن"
        verbose_name_plural = "دستگاه‌های پوش نوتیفیکیشن"
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['registration_id']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['type', 'is_active']),
        ]

    def __str__(self):
        user_display = self.user.username if self.user else "کاربر مهمان"
        return f"{self.name or self.type} - {user_display} ({self.registration_id[:16]}...)"

    def send_message(self, title, body, url=None, icon=None, data=None):
        """
        Send push notification directly to this device.
        """
        return PushDevice.objects.filter(pk=self.pk).send_message(
            title=title, body=body, url=url, icon=icon, data=data
        )
