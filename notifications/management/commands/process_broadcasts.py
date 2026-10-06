import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from notifications.models import Notification
from notifications.broadcast import load_assets, deliver_one

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "پردازش و ارسال پیام‌های همگانی PENDING در دسته‌های ۴۰ عددی"

    def handle(self, *args, **options):
        ids = list(
            Notification.objects.filter(
                status=Notification.Status.PENDING,
                broadcast__isnull=False
            )
            .order_by("pk")
            .values_list("pk", flat=True)[:40]
        )
        if not ids:
            self.stdout.write("پیام همگانی در صف وجود ندارد.")
            return

        assets = {}
        done = 0
        for pk in ids:
            stop = False
            with transaction.atomic():
                n = (
                    Notification.objects.select_for_update(skip_locked=True, of=("self",))
                    .select_related("broadcast", "user")
                    .filter(pk=pk, status=Notification.Status.PENDING)
                    .first()
                )
                if n is None:
                    continue
                try:
                    a = assets.get(n.broadcast_id) or assets.setdefault(n.broadcast_id, load_assets(n.broadcast))
                    stop = deliver_one(n, a)
                except Exception:
                    logger.exception("broadcast deliver failed %s", pk)
                    n.status = Notification.Status.FAILED
                    n.error_text = "خطای داخلی"
                    n.save(update_fields=["status", "error_text"])
                done += 1
            if stop:
                break
        self.stdout.write(self.style.SUCCESS(f"{done} ردیف پیام همگانی پردازش شد."))
