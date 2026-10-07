from django.core.management.base import BaseCommand

from notifications.broadcast import run_process_broadcasts


class Command(BaseCommand):
    help = "ارسال دستی پیام‌های همگانی PENDING (پوسته‌ی نازک روی همان تابعی که Celery صدا می‌زند)."

    def add_arguments(self, parser):
        parser.add_argument("--max-seconds", type=int, default=120)

    def handle(self, *args, **options):
        # توجه: تست‌های قدیمی Command().handle() را بدون آرگومان صدا می‌زنند؛ پس options.get
        stats = run_process_broadcasts(max_seconds=options.get("max_seconds", 120))
        self.stdout.write(self.style.SUCCESS(
            f"{stats['finalized']} ردیف نهایی شد؛ {stats['waiting']} ردیف منتظر خطای موقت؛ منقضی‌شده: {stats['expired']}."))
