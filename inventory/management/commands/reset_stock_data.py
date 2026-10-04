from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction

from catalog.models import Item
from inventory.models import Purchase, PurchaseLine, StockLot, StockMovement


class Command(BaseCommand):
    help = ("فقط فاز توسعه: همه‌ی داده‌ی انبار (حرکت، لات، خرید) را پاک می‌کند و میانگین قیمت‌ها را صفر می‌کند. "
            "کالاها و پروژه‌ها دست نمی‌خورند. بدون --yes فقط می‌شمارد.")

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true")
        parser.add_argument("--force", action="store_true", help="بیرون از حالت DEBUG هم اجرا شود")

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("این دستور فقط برای فاز توسعه است؛ بیرون از DEBUG فقط با --force اجرا می‌شود.")
        counts = {"حرکت انبار": StockMovement.objects.count(), "لات": StockLot.objects.count(),
                  "ردیف خرید": PurchaseLine.objects.count(), "سند خرید": Purchase.objects.count()}
        for label, n in counts.items():
            self.stdout.write(f"{label}: {n}")
        if not opts["yes"]:
            self.stdout.write(self.style.WARNING("چیزی پاک نشد. برای پاک‌کردن --yes بزنید (قبلش بکاپ بگیرید)."))
            return
        with transaction.atomic():
            StockMovement.objects.all().delete()
            StockLot.objects.all().delete()
            PurchaseLine.objects.all().delete()
            Purchase.objects.all().delete()
            Item.objects.update(moving_average_cost=0)
        self.stdout.write(self.style.SUCCESS("داده‌ی انبار پاک شد؛ حالا از «ورود گروهی موجودی اولیه» دوباره ثبت کنید."))
