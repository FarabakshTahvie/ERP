import logging
from django.db import transaction
from django.utils import timezone
from .models import Notification, NotificationPolicy, ChannelPolicy, NotificationType
from utils.sms import SMSService
from utils.push_notification import NajvaService

logger = logging.getLogger(__name__)

SMS_TEMPLATE_TYPES = {NotificationType.INVOICE_ISSUED}   # فقط نوعی که قالب تاییدشده‌ی sms.ir دارد


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
    if not tokens:   # دستگاه پوش ندارد؛ خطا نیست، پیام در مرکز اعلان داخل برنامه می‌ماند
        notification.status = Notification.Status.IN_APP
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
    """پیامک فقط برای نوعی که قالب تاییدشده دارد. متن آزاد عمداً حذف شده (هزینه و قالب‌نداشتن)."""
    if notification.notification_type not in SMS_TEMPLATE_TYPES:
        logger.info("no sms template for %s; skipped", notification.notification_type)
        return False
    phone = getattr(notification.user, "phone_number", None)
    if not phone:
        notification.status = Notification.Status.FAILED
        notification.save(update_fields=["status"])
        return False

    data = notification.extra_data or {}
    result = SMSService().send_invoice_issued(
        mobile=phone,
        name=notification.user.first_name or "کاربر گرامی",
        number=data.get("invoice_number", ""),
        username=data.get("username", ""),
        password=data.get("password") or "رمز فعلی شما",
        link=notification.short_path,          # فقط مسیر، مثل s/abcde
    )

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


def notify_users(users, *, notification_type, title, body, real_target_url=""):
    """اعلان برای چند نفر. بعد از commit ارسال می‌شود (خطای ارسال تراکنش اصلی را خراب نمی‌کند)،
    تکراری‌ها یکی می‌شوند و کاربر غیرفعال اعلان نمی‌گیرد."""
    ids, seen = [], set()
    for user in users:
        if user is not None and user.is_active and user.pk not in seen:
            seen.add(user.pk)
            ids.append(user.pk)
    if not ids:
        return

    def send():
        from django.contrib.auth import get_user_model
        for user in get_user_model().objects.filter(pk__in=ids, is_active=True):
            try:
                create_notification(notification_type=notification_type, user=user, title=title,
                                    body=body, real_target_url=real_target_url)
            except Exception:
                logger.exception("notify failed for user %s", user.pk)

    transaction.on_commit(send)


def resend_notification(notification, *, actor):
    """ارسال دوباره‌ی اعلان ناموفق (فقط مدیر). پیامک پیش‌فاکتور مجاز نیست: رمزش بعد از ارسال پاک شده."""
    from core.capabilities import can
    if not can(actor, "notifications.manage"):
        raise ValueError("فقط مدیر می‌تواند اطلاع‌رسانی را دوباره بفرستد.")
    if notification.status != Notification.Status.FAILED:
        raise ValueError("فقط اطلاع‌رسانی ناموفق دوباره فرستاده می‌شود.")
    if notification.notification_type == NotificationType.INVOICE_ISSUED:
        raise ValueError("پیامک پیش‌فاکتور حاوی رمز است و دوباره فرستاده نمی‌شود؛ از «بازنشانی رمز» در بخش افراد استفاده کنید.")
    if notification.notification_type == NotificationType.BROADCAST:
        raise ValueError("ارسال دوباره‌ی پیام همگانی از این بخش مجاز نیست؛ از صفحه‌ی جزئیات پیام همگانی اقدام کنید.")
    Notification.objects.filter(pk=notification.pk).update(status=Notification.Status.PENDING)
    notification.refresh_from_db()
    dispatch_notification(notification)
    notification.refresh_from_db()
    return notification
