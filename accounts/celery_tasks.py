import logging

from celery import shared_task

from utils.sms import SMSService
from .models import OTPCode

logger = logging.getLogger(__name__)


def _is_transient(result):
    """خطای شبکه (http_status=None)، ۵xx و ۴۲۹ موقتی‌اند. نبودن کلید http_status یعنی خطای تنظیمات؛ موقتی نیست."""
    http = result.get("http_status", 0)
    return http is None or http >= 500 or http == 429


@shared_task(bind=True, name="accounts.send_otp_sms", ignore_result=True, max_retries=2,
             soft_time_limit=25, time_limit=35)
def send_otp_sms_task(self, otp_id, mobile, code):
    # کد خام را هرگز لاگ نکن؛ مقدار بازگشتی هم نداریم (Celery آن را لاگ می‌کند).
    result = SMSService().send_otp(mobile=mobile, code=code)
    if result.get("success"):
        return None
    if _is_transient(result) and self.request.retries < self.max_retries:
        raise self.retry(countdown=3)
    OTPCode.objects.filter(pk=otp_id, is_used=False).update(is_used=True)   # درخواست بعدی کد تازه می‌سازد
    logger.error("OTP sms failed for otp %s: %s", otp_id, str(result.get("error"))[:120])
    return None
