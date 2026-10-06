import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from notifications.broadcast import (
    FAIL_ALL, WAIT, AssetError, channel_open, deliver_one, expire_stale, fail_pending, load_assets,
)
from notifications.models import Notification

logger = logging.getLogger(__name__)
BATCH = 40


class Command(BaseCommand):
    help = "ارسال پیام‌های همگانی PENDING در دسته‌های ۴۰ تایی؛ هر ردیف تراکنش کوتاه خودش را دارد."

    def handle(self, *args, **options):
        expired = expire_stale()
        open_channels = [c for c in ("push", "sms") if channel_open(c)]
        rows = list(
            Notification.objects.filter(status=Notification.Status.PENDING, broadcast__isnull=False)
            .filter(Q(broadcast__is_dry_run=True) | Q(broadcast__channel__in=open_channels))
            .order_by("pk").values_list("pk", "broadcast__channel")[:BATCH])
        if not rows:
            self.stdout.write(f"پیام همگانی در صف نیست. منقضی‌شده: {expired}")
            return

        assets, blocked, done = {}, set(), 0
        for pk, channel in rows:
            if channel in blocked:
                continue
            signal, broadcast_id = None, None
            try:
                with transaction.atomic():
                    n = (Notification.objects.select_for_update(skip_locked=True, of=("self",))
                         .select_related("broadcast", "user")
                         .filter(pk=pk, status=Notification.Status.PENDING).first())
                    if n is None:
                        continue
                    broadcast_id = n.broadcast_id
                    if broadcast_id not in assets:
                        assets[broadcast_id] = load_assets(n.broadcast)
                    signal = deliver_one(n, assets[broadcast_id])
                    if signal == FAIL_ALL:
                        fail_pending(n.broadcast_id, n.error_text or "خطای سراسری")
            except AssetError as e:
                fail_pending(broadcast_id, str(e))
                continue
            except Exception:
                logger.exception("broadcast deliver failed %s", pk)
                # نتیجه‌ی ارسال نامعلوم است؛ برای جلوگیری از ارسال تکراری FAILED می‌شود (مدیر دستی «ارسال دوباره» می‌زند)
                Notification.objects.filter(pk=pk, status=Notification.Status.PENDING).update(
                    status=Notification.Status.FAILED, error_text="خطای داخلی")
                continue
            done += 1
            if signal in (WAIT, FAIL_ALL):
                blocked.add(channel)
        self.stdout.write(self.style.SUCCESS(f"{done} ردیف پردازش شد؛ منقضی‌شده: {expired}."))
