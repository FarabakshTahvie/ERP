import uuid
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


import secrets
SHORT_CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"   # بدون کاراکترهای گیج‌کننده

def _new_short_code(length=7):
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(length))


class NotificationType(models.TextChoices):
    INVOICE_ISSUED = "invoice_issued", "صدور پیش‌فاکتور"
    PROGRESS_UPDATE = "progress_update", "پیشرفت مراحل کار"
    LOW_STOCK = "low_stock", "کمبود موجودی انبار"
    MANUAL = "manual", "پیام دستی"
    STAGE_APPROVAL_REQUEST = "stage_approval_request", "درخواست تایید مرحله"


class ChannelPolicy(models.TextChoices):
    SMS_ONLY = "sms_only", "فقط پیامک"
    PUSH_ONLY = "push_only", "فقط پوش"
    PUSH_AND_SMS = "push_and_sms", "پوش و پیامک با هم"
    PUSH_THEN_SMS_FALLBACK = "push_then_sms_fallback", "پوش، اگه دیده نشد پیامک"


class NotificationPolicy(models.Model):
    """سیاست ارسال هر نوع پیام — از پنل ادمین قابل تغییره، بدون نیاز به دیپلوی."""
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, unique=True, verbose_name="نوع پیام")
    channel_policy = models.CharField(max_length=30, choices=ChannelPolicy.choices, verbose_name="سیاست کانال")
    fallback_after_minutes = models.PositiveIntegerField(default=15, verbose_name="مهلت قبل از پیامک جایگزین (دقیقه)")

    class Meta:
        verbose_name = "سیاست اطلاع‌رسانی"
        verbose_name_plural = "سیاست‌های اطلاع‌رسانی"

    def __str__(self):
        return f"{self.get_notification_type_display()} → {self.get_channel_policy_display()}"


class Notification(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار ارسال"
        PUSH_SENT = "push_sent", "پوش ارسال شد"
        SEEN = "seen", "دیده شد"
        SMS_SENT = "sms_sent", "پیامک ارسال شد"
        FAILED = "failed", "ناموفق"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="شناسه یکتا")
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, db_index=True, verbose_name="نوع پیام")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications", verbose_name="گیرنده")
    title = models.CharField(max_length=255, verbose_name="عنوان")
    body = models.TextField(verbose_name="متن پیام")
    real_target_url = models.CharField(max_length=500, blank=True, verbose_name="لینک مقصد واقعی")
    short_code = models.CharField(max_length=12, unique=True, null=True, blank=True, editable=False, verbose_name="کد کوتاه لینک")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="وضعیت")
    push_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال پوش")
    sms_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان ارسال پیامک")
    seen_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان دیده‌شدن")
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="داده‌ی اضافی برای تمپلیت")

    related_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    class Meta:
        verbose_name = "اطلاع‌رسانی"
        verbose_name_plural = "اطلاع‌رسانی‌ها"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "seen_at"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["related_content_type", "related_object_id"]),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} → {self.user}"

    def save(self, *args, **kwargs):
        if not self.short_code:
            for _ in range(10):
                candidate = _new_short_code()
                if not Notification.objects.filter(short_code=candidate).exists():
                    self.short_code = candidate
                    break
        super().save(*args, **kwargs)

    @property
    def short_path(self):
        """مسیر بدون دامنه و بدون اسلش ابتدایی — برای پارامتر LINK پترن پیامک."""
        return f"s/{self.short_code}/" if (self.short_code and self.real_target_url) else ""

    @property
    def tracking_url(self):
        return f"{settings.SITE_BASE_URL.rstrip('/')}/{self.short_path}" if self.short_path else ""


class NotificationClickEvent(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="click_events", verbose_name="اطلاع‌رسانی")
    channel = models.CharField(max_length=10, choices=[("push", "پوش"), ("sms", "پیامک")], verbose_name="کانال")
    clicked_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان کلیک")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آی‌پی")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="User Agent")

    class Meta:
        verbose_name = "رویداد کلیک"
        verbose_name_plural = "رویدادهای کلیک"
        indexes = [
            models.Index(fields=["notification", "clicked_at"]),
        ]
