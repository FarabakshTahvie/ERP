from django.conf import settings
from django.utils import timezone

from .models import Notification, NotificationPolicy, ChannelPolicy, NotificationType
from utils.sms import SMSService
from utils.push_notification import NajvaService


def create_notification(*, notification_type, user, title, body, real_target_url="", related_object=None, dispatch_immediately=True):
    notification = Notification.objects.create(
        notification_type=notification_type, user=user, title=title, body=body, real_target_url=real_target_url,
    )
    if related_object is not None:
        notification.related_object = related_object
        notification.save(update_fields=["related_content_type", "related_object_id"])

    if dispatch_immediately:
        try:
            dispatch_notification(notification)
        except Exception:
            pass
    return notification


def dispatch_notification(notification: Notification):
    policy = NotificationPolicy.objects.filter(notification_type=notification.notification_type).first()
    channel_policy = policy.channel_policy if policy else ChannelPolicy.PUSH_ONLY

    if channel_policy == ChannelPolicy.SMS_ONLY:
        send_sms_channel(notification)
    elif channel_policy == ChannelPolicy.PUSH_ONLY:
        send_push_channel(notification)
    elif channel_policy == ChannelPolicy.PUSH_AND_SMS:
        send_push_channel(notification)
        send_sms_channel(notification)
    elif channel_policy == ChannelPolicy.PUSH_THEN_SMS_FALLBACK:
        send_push_channel(notification)


def send_push_channel(notification: Notification):
    from utils.models import PushDevice
    tokens = list(PushDevice.objects.filter(user=notification.user, is_active=True).values_list("registration_id", flat=True))
    if not tokens:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])
        return

    link = f"{notification.tracking_url}?ch=push" if notification.tracking_url else None
    result = NajvaService().send(title=notification.title, body=notification.body, subscriber_tokens=tokens, url=link)

    notification.status = Notification.Status.PUSH_SENT if result.get("success") else Notification.Status.FAILED
    notification.push_sent_at = timezone.now() if result.get("success") else None
    notification.save(update_fields=["status", "push_sent_at"])


def send_sms_channel(notification: Notification):
    phone = getattr(notification.user, "phone_number", None)
    if not phone:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])
        return

    sms_service = SMSService()
    link = f"{notification.tracking_url}?ch=sms" if notification.tracking_url else ""

    if notification.notification_type == NotificationType.INVOICE_ISSUED:
        data = notification.extra_data
        sms_service.send_invoice_issued(
            mobile=phone,
            name=notification.user.get_full_name() or notification.user.username,
            number=data.get("invoice_number", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
            link=link or notification.real_target_url,
        )
    else:
        text = f"{notification.title}\n{notification.body}"
        if link:
            text += f"\n{link}"
        sms_service.send_text(mobile=phone, message=text)

    notification.status = Notification.Status.SMS_SENT
    notification.sms_sent_at = timezone.now()
    notification.save(update_fields=["status", "sms_sent_at"])
