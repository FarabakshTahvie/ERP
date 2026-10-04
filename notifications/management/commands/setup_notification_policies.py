from django.core.management.base import BaseCommand

from notifications.models import ChannelPolicy as C, NotificationPolicy, NotificationType as T

# پیامک فقط برای پیش‌فاکتور. هر نوع تازه‌ای که قالب sms.ir گرفت، این‌جا و در
# notifications/services.py::SMS_TEMPLATE_TYPES عوض می‌شود.
DEFAULTS = {
    T.INVOICE_ISSUED: (C.SMS_ONLY, 15),
    T.STAGE_APPROVAL_REQUEST: (C.PUSH_ONLY, 15),   # TODO(پیامک design_approval_request)
    T.STAGE_ASSIGNED: (C.PUSH_ONLY, 15),
    T.PART_REQUEST: (C.PUSH_ONLY, 15),
    T.LOW_STOCK: (C.PUSH_ONLY, 15),
    T.PROGRESS_UPDATE: (C.PUSH_ONLY, 15),
    T.MANUAL: (C.PUSH_ONLY, 15),
}


class Command(BaseCommand):
    help = "ساخت سیاست پیش‌فاکتور اطلاع‌رسانی برای هر نوع پیام. بدون --force ردیف موجود را دست نمی‌زند."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="ردیف‌های موجود هم به پیش‌فرض برگردند")

    def handle(self, *args, **options):
        made = reset = 0
        for ntype, (policy, minutes) in DEFAULTS.items():
            obj, created = NotificationPolicy.objects.get_or_create(
                notification_type=ntype, defaults={"channel_policy": policy, "fallback_after_minutes": minutes})
            made += int(created)
            if not created and options["force"] and (obj.channel_policy, obj.fallback_after_minutes) != (policy, minutes):
                obj.channel_policy, obj.fallback_after_minutes = policy, minutes
                obj.save()
                reset += 1
        self.stdout.write(self.style.SUCCESS(f"{made} سیاست ساخته شد، {reset} سیاست به پیش‌فرض برگشت."))
