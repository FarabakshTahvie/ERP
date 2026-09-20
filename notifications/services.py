import logging
from django.utils import timezone
from .models import Notification, NotificationPolicy, ChannelPolicy, NotificationType
from utils.sms import SMSService
from utils.push_notification import NajvaService

logger = logging.getLogger(__name__)


def create_notification(*, notification_type, user, title, body, real_target_url="",
                        related_object=None, extra_data=None, dispatch_immediately=True):
    notification = Notification.objects.create(
        notification_type=notification_type, user=user, title=title, body=body,
        real_target_url=real_target_url, extra_data=extra_data or {},
    )
    if related_object is not None:
        notification.related_object = related_object
        notification.save(update_fields=["related_content_type", "related_object_id"])
    if dispatch_immediately:
        dispatch_notification(notification)   # خطاها داخلش مهار و لاگ می‌شوند
    return notification


def dispatch_notification(notification):
    try:
        policy = NotificationPolicy.objects.filter(notification_type=notification.notification_type).first()
        cp = policy.channel_policy if policy else ChannelPolicy.PUSH_ONLY
        if cp == ChannelPolicy.SMS_ONLY:
            send_sms_channel(notification)
        elif cp == ChannelPolicy.PUSH_ONLY:
            send_push_channel(notification)
        elif cp == ChannelPolicy.PUSH_AND_SMS:
            send_push_channel(notification)
            send_sms_channel(notification)
        elif cp == ChannelPolicy.PUSH_THEN_SMS_FALLBACK:
            if not send_push_channel(notification):   # پوش شکست خورد (بدون دستگاه/خطا) → همین حالا پیامک
                send_sms_channel(notification)
    except Exception:
        logger.exception("dispatch failed for notification %s", notification.pk)
        Notification.objects.filter(pk=notification.pk).update(status=Notification.Status.FAILED)


def send_push_channel(notification) -> bool:
    from utils.models import PushDevice
    tokens = list(PushDevice.objects.filter(user=notification.user, is_active=True)
                  .values_list("registration_id", flat=True))
    if not tokens:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])
        return False

    link = f"{notification.tracking_url}?ch=push" if notification.tracking_url else None
    result = NajvaService().send(title=notification.title, body=notification.body,
                                 subscriber_tokens=tokens, url=link)
    invalid = result.get("invalid_tokens") or []
    if invalid:
        PushDevice.objects.filter(registration_id__in=invalid).update(is_active=False)

    ok = bool(result.get("success"))
    notification.status = Notification.Status.PUSH_SENT if ok else Notification.Status.FAILED
    notification.push_sent_at = timezone.now() if ok else None
    notification.save(update_fields=["status", "push_sent_at"])
    return ok


def send_sms_channel(notification) -> bool:
    phone = getattr(notification.user, "phone_number", None)
    if not phone:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])
        return False

    sms = SMSService()
    if notification.notification_type == NotificationType.INVOICE_ISSUED:
        data = notification.extra_data or {}
        name = notification.user.first_name or "کاربر گرامی"
        result = sms.send_invoice_issued(
            mobile=phone,
            name=name,
            number=data.get("invoice_number", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
            link=notification.short_path,          # فقط مسیر، مثل s/abcde
        )
    else:
        text = f"{notification.title}\n{notification.body}"
        if notification.tracking_url:
            text += f"\n{notification.tracking_url}"
        result = sms.send_text(mobile=phone, message=text)

    # رمز خام نباید در دیتابیس بماند
    extra = dict(notification.extra_data or {})
    if "password" in extra:
        extra["password"] = ""
        notification.extra_data = extra

    ok = bool(result.get("success"))
    notification.status = Notification.Status.SMS_SENT if ok else Notification.Status.FAILED
    notification.sms_sent_at = timezone.now() if ok else None
    notification.save(update_fields=["status", "sms_sent_at", "extra_data"])
    return ok
