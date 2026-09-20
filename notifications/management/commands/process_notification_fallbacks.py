import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from notifications.models import Notification, NotificationPolicy, ChannelPolicy
from notifications.services import send_sms_channel

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "ارسال پیامک جایگزین برای پیام‌های دیده‌نشده — هر ۵ دقیقه با کرون"

    def handle(self, *args, **options):
        policies = {
            p.notification_type: p
            for p in NotificationPolicy.objects.filter(channel_policy=ChannelPolicy.PUSH_THEN_SMS_FALLBACK)
        }
        if not policies:
            return

        with transaction.atomic():
            candidates = list(
                Notification.objects.select_for_update(skip_locked=True).filter(
                    status=Notification.Status.PUSH_SENT,
                    notification_type__in=policies.keys(),
                    seen_at__isnull=True,
                )
            )
            due = [
                n for n in candidates
                if n.push_sent_at and timezone.now() >= n.push_sent_at + timedelta(minutes=policies[n.notification_type].fallback_after_minutes)
            ]
            for notification in due:
                try:
                    send_sms_channel(notification)
                except Exception as e:
                    logger.exception("Error sending fallback SMS for notification %s: %s", notification.pk, e)
                    Notification.objects.filter(pk=notification.pk).update(status=Notification.Status.FAILED)
        self.stdout.write(self.style.SUCCESS(f"{len(due)} پیامک جایگزین پردازش شد."))
