import logging

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from utils.sms import SMSService
from utils.utils import generate_random_code
from .models import User, OTPCode

logger = logging.getLogger(__name__)


@transaction.atomic
def create_staff_account(*, first_name, last_name, phone_number, role, specialties=None):
    """ایجاد حساب کاربری پرسنل/تکنسین با رمز عبور تصادفی و نام کاربری منطبق بر شماره موبایل."""
    if User.objects.filter(phone_number=phone_number).exists():
        raise ValidationError("کاربری با این شماره موبایل قبلاً در سامانه ثبت شده است.")
    if User.objects.filter(username=phone_number).exists():
        raise ValidationError("نام کاربری مربوط به این شماره موبایل قبلاً ثبت شده است.")

    raw_password = generate_random_code(length=10, digits_only=False)
    user = User(
        username=phone_number,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=role,
        is_staff=True,
        must_change_password=False,
    )
    user.set_password(raw_password)
    user.save()
    if specialties:
        user.specialties.set(specialties)
    return user, raw_password


def get_or_create_active_otp(phone_number, purpose, user=None, ip_address=None):
    """
    اگر کد فعال (استفاده‌نشده و منقضی‌نشده) برای همین شماره و همین کاربرد وجود داشته باشد،
    همان را برمی‌گردانیم و پیامک تازه‌ای ارسال نمی‌شود (raw_code=None، چون کد قبلی هش‌شده
    و قابل بازیابی نیست؛ کاربر باید همان کدی که قبلاً دریافت کرده را وارد کند).
    وگرنه کد جدید ساخته و raw_code واقعی برمی‌گردد تا پیامک شود.

    خروجی: (otp, raw_code_or_None, is_new)
    """
    existing = OTPCode.objects.filter(
        phone_number=phone_number, purpose=purpose,
        is_used=False, expires_at__gt=timezone.now(),
    ).order_by("-created_at").first()
    if existing:
        return existing, None, False
    otp, raw_code = OTPCode.generate(phone_number=phone_number, purpose=purpose, user=user, ip_address=ip_address)
    return otp, raw_code, True


def otp_remaining_seconds(phone_number, purpose):
    """چند ثانیه تا انقضای کد فعال فعلی باقی مانده؛ اگر کد فعالی نباشد صفر."""
    otp = OTPCode.objects.filter(
        phone_number=phone_number, purpose=purpose,
        is_used=False, expires_at__gt=timezone.now(),
    ).order_by("-created_at").first()
    if not otp:
        return 0
    return max(int((otp.expires_at - timezone.now()).total_seconds()), 0)


def dispatch_otp_sms(otp, raw_code):
    """True: پیامک در صف رفت (یا مستقیم فرستاده شد). False: ارسال ممکن نبود؛ کد پاک شد و کاربر خطا می‌بیند.
    اگر Celery/ردیس در دسترس نباشد همان مسیر قبلی (ارسال مستقیم) اجرا می‌شود تا ورود هرگز نخوابد."""
    from .celery_tasks import send_otp_sms_task
    try:
        send_otp_sms_task.delay(otp.pk, otp.phone_number, raw_code)
        return True
    except Exception:
        logger.exception("OTP sms could not be queued; sending directly")
    result = SMSService().send_otp(mobile=otp.phone_number, code=raw_code)
    if result.get("success"):
        return True
    otp.delete()
    return False
