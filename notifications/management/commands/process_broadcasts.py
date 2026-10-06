import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.utils.timezone import now

from utils.sms import SMSService
from utils.push_notification import NajvaService
from utils.models import PushDevice
from notifications.models import Broadcast, Notification

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "پردازش و ارسال پیام‌های همگانی PENDING در دسته‌های ۴۰ عددی"

    def handle(self, *args, **options):
        # دریافت ۴۰ پیام همگانی در صف ارسال با قفل سطری اتمیک برای ایمنی همزمانی
        with transaction.atomic():
            pending_notifs = list(
                Notification.objects.select_for_update(skip_locked=True, of=("self",))
                .filter(
                    status=Notification.Status.PENDING,
                    broadcast__isnull=False
                )
                .select_related("broadcast", "user")[:40]
            )

            if not pending_notifs:
                self.stdout.write("پیام همگانی در صف وجود ندارد.")
                return

            for notif in pending_notifs:
                broadcast = notif.broadcast
                user = notif.user

                # بررسی حالت اجرای آزمایشی (dry-run)
                if broadcast.is_dry_run:
                    notif.status = Notification.Status.PUSH_SENT if broadcast.channel == "push" else Notification.Status.SMS_SENT
                    if broadcast.channel == "push":
                        notif.push_sent_at = now()
                    else:
                        notif.sms_sent_at = now()
                    notif.error_text = "آزمایشی"
                    notif.save(update_fields=["status", "push_sent_at", "sms_sent_at", "error_text"])
                    continue

                if broadcast.channel == "push":
                    # ارسال پوش
                    tokens = list(
                        PushDevice.objects.filter(user=user, is_active=True)
                        .values_list("registration_id", flat=True)
                    )
                    if not tokens:
                        notif.status = Notification.Status.IN_APP
                        notif.save(update_fields=["status"])
                        continue

                    # ساخت آدرس‌های تصویر و آیکون
                    # نجوا تصویر را از آدرس عمومی دریافت می‌کند، پس آدرس عمومی /b/<name> را می‌دهیم
                    base_url = settings.SITE_BASE_URL.rstrip('/')
                    icon_url = f"{base_url}/b/{broadcast.icon_name}" if broadcast.icon_name else f"{base_url}/static/img/icon-192.png"
                    image_url = f"{base_url}/b/{broadcast.image_name}" if broadcast.image_name else None
                    click_url = f"{notif.tracking_url}?ch=push" if notif.tracking_url else base_url

                    result = NajvaService().send(
                        title=broadcast.title or "فرابخش تهویه",
                        body=broadcast.body,
                        subscriber_tokens=tokens,
                        url=click_url,
                        ttl=broadcast.ttl_hours,
                        icon_url=icon_url,
                        image_url=image_url
                    )

                    invalid = result.get("invalid_tokens") or []
                    if invalid:
                        PushDevice.objects.filter(registration_id__in=invalid).update(is_active=False)

                    ok = bool(result.get("success"))
                    notif.status = Notification.Status.PUSH_SENT if ok else Notification.Status.FAILED
                    notif.push_sent_at = now() if ok else None
                    if not ok:
                        notif.error_text = result.get("error", "خطای ارسال پوش")[:255]
                    notif.save(update_fields=["status", "push_sent_at", "error_text"])

                elif broadcast.channel == "sms":
                    # ارسال پیامک بدون قالب
                    phone = getattr(user, "phone_number", None)
                    if not phone:
                        notif.status = Notification.Status.FAILED
                        notif.error_text = "فاقد شماره همراه"
                        notif.save(update_fields=["status", "error_text"])
                        continue

                    text = broadcast.body
                    # در پیامک آزاد، اگر لینک تعریف شده باشد، لینک ردیاب کوتاه شده به انتهای متن اضافه می‌شود.
                    if notif.tracking_url:
                        text += f"\n{notif.tracking_url}?ch=sms"

                    # امضا به انتهای متن اضافه می‌شود
                    text += "\nفرابخش تهویه"

                    result = SMSService().send_text(mobile=phone, message=text)
                    ok = bool(result.get("success"))
                    notif.status = Notification.Status.SMS_SENT if ok else Notification.Status.FAILED
                    notif.sms_sent_at = now() if ok else None
                    if not ok:
                        notif.error_text = result.get("error", "خطای ارسال پیامک")[:255]
                    notif.save(update_fields=["status", "sms_sent_at", "error_text"])

            self.stdout.write(self.style.SUCCESS(f"تعداد {len(pending_notifs)} پیام همگانی پردازش شد."))
