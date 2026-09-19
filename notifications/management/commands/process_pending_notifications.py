from django.core.management.base import BaseCommand
from django.db import transaction

from notifications.models import Notification
from notifications.services import dispatch_notification


class Command(BaseCommand):
    help = "ارسال پیام‌های pending — هر ۱ دقیقه با کرون"

    def handle(self, *args, **options):
        with transaction.atomic():
            pending = list(
                Notification.objects.select_for_update(skip_locked=True).filter(status=Notification.Status.PENDING)
            )
            for notification in pending:
                dispatch_notification(notification)
        self.stdout.write(self.style.SUCCESS(f"{len(pending)} پیام پردازش شد."))
