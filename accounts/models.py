import secrets
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.conf import settings
from simple_history.models import HistoricalRecords
from utils.utils import validate_national_code


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'manager', 'مدیر'
        EMPLOYEE = 'employee', 'تکنسین'
        CLIENT = 'client', 'کارفرما'
        PARTNER = 'partner', 'شریک تجاری'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        verbose_name="نقش کاربر"
    )
    phone_number = models.CharField(
        max_length=11,
        unique=True,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^09\d{9}$',
                message="شماره موبایل معتبر نیست (باید ۱۱ رقم و با 09 شروع شود، مثال: 09123456789)"
            )
        ],
        verbose_name="شماره موبایل"
    )
    national_code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        validators=[validate_national_code],
        verbose_name="کد ملی"
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name="تصویر پروفایل"
    )
    specialties = models.ManyToManyField(
        'core.Specialty',
        blank=True,
        related_name='technicians',
        verbose_name="تخصص‌ها",
    )
    party = models.ForeignKey(
        'core.Party',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="طرف‌حساب مرتبط (برای نقش کارفرما/شریک تجاری)",
    )
    must_change_password = models.BooleanField(default=False, verbose_name="نیاز به تغییر رمز در ورود بعدی")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if self.avatar:
            from utils.image_utils import optimize_image
            optimized = optimize_image(self.avatar, profile_name="avatar")
            if optimized is not self.avatar:
                self.avatar.save(optimized.name, optimized, save=False)
        super().save(*args, **kwargs)


class OTPCode(models.Model):
    """
    کد یکبارمصرف. مدل مجزا از سیستم اطلاع‌رسانی چون OTP باید همزمان (synchronous)
    و فوری ارسال بشه، نه از صف/کرون عبور کنه.
    """

    class Purpose(models.TextChoices):
        LOGIN = "login", "ورود"
        PASSWORD_RESET = "password_reset", "فراموشی رمز عبور"
        PHONE_VERIFICATION = "phone_verification", "تایید شماره موبایل"

    phone_number = models.CharField(max_length=11, verbose_name="شماره موبایل")
    purpose = models.CharField(max_length=30, choices=Purpose.choices, verbose_name="نوع کاربرد")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="otp_codes", verbose_name="کاربر (در صورت وجود)",
    )
    code_hash = models.CharField(max_length=128, verbose_name="هش کد")
    is_used = models.BooleanField(default=False, verbose_name="مصرف شده")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان مصرف")
    attempt_count = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد تلاش ناموفق")
    expires_at = models.DateTimeField(verbose_name="زمان انقضا")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آی‌پی درخواست‌دهنده")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")

    MAX_ATTEMPTS = 5

    class Meta:
        verbose_name = "کد یکبارمصرف"
        verbose_name_plural = "کدهای یکبارمصرف"
        indexes = [
            models.Index(fields=['phone_number', 'purpose', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"OTP({self.phone_number}, {self.purpose})"

    @classmethod
    def generate(cls, phone_number, purpose, user=None, ip_address=None, ttl_minutes=None, length=None):
        ttl_minutes = ttl_minutes or getattr(settings, 'OTP_EXPIRY_MINUTES', 2)
        length = length or getattr(settings, 'OTP_LENGTH', 5)
        cls.objects.filter(phone_number=phone_number, purpose=purpose, is_used=False).update(is_used=True)
        raw_code = "".join(secrets.choice("0123456789") for _ in range(length))
        instance = cls.objects.create(
            phone_number=phone_number,
            purpose=purpose,
            user=user,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timezone.timedelta(minutes=ttl_minutes),
            ip_address=ip_address,
        )
        return instance, raw_code

    @classmethod
    def verify(cls, phone_number, purpose, raw_code):
        otp = (
            cls.objects.filter(phone_number=phone_number, purpose=purpose, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not otp:
            return False, "کد یافت نشد یا قبلاً استفاده شده است."
        if otp.expires_at < timezone.now():
            return False, "کد منقضی شده است."
        if otp.attempt_count >= cls.MAX_ATTEMPTS:
            return False, "تعداد تلاش‌های مجاز به پایان رسیده است."
        if not check_password(raw_code, otp.code_hash):
            otp.attempt_count = models.F("attempt_count") + 1
            otp.save(update_fields=["attempt_count"])
            return False, "کد وارد شده صحیح نیست."
        otp.is_used = True
        otp.used_at = timezone.now()
        otp.save(update_fields=["is_used", "used_at"])
        return True, otp


class LoginHistory(models.Model):
    class Result(models.TextChoices):
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="login_history", verbose_name="کاربر",
    )
    username_attempted = models.CharField(max_length=150, blank=True, verbose_name="نام‌کاربری وارد شده")
    result = models.CharField(max_length=10, choices=Result.choices, verbose_name="نتیجه")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="آی‌پی")
    user_agent = models.CharField(max_length=500, blank=True, verbose_name="User-Agent خام")
    browser = models.CharField(max_length=100, blank=True, verbose_name="مرورگر")
    os = models.CharField(max_length=100, blank=True, verbose_name="سیستم‌عامل")
    device_type = models.CharField(max_length=20, blank=True, verbose_name="نوع دستگاه")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان")

    class Meta:
        verbose_name = "تاریخچه ورود"
        verbose_name_plural = "تاریخچه‌ی ورودها"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["ip_address", "-created_at"]),
            models.Index(fields=["result", "-created_at"]),
        ]

    def __str__(self):
        from utils.jalali import jalali_str
        who = self.user or self.username_attempted
        return f"{who} - {self.get_result_display()} @ {jalali_str(self.created_at, fmt='%Y/%m/%d %H:%M')}"
