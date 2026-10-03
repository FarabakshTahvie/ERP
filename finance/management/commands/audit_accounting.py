from collections import defaultdict
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from inventory.models import StockLot, StockMovement
from finance import accounting


class Command(BaseCommand):
    help = "چک هویت‌های حسابداری انبار و گزارش ناهم‌خوانی‌ها (فقط می‌خواند، چیزی تغییر نمی‌دهد)."

    def add_arguments(self, parser):
        parser.add_argument("--threshold", type=int, default=50_000_000,
                            help="بهای واحد بالاتر از این مقدار مشکوک گزارش شود")

    def handle(self, *args, **opts):
        w = self.stdout.write
        i = accounting.stock_integrity()
        w("== هویت کلی ==")
        w(f"ورودی‌ها: {i['in']}  خروجی‌ها: {i['out']}  ارزش لات‌ها: {i['stock']}  اختلاف: {i['diff']}")
        w(f"ورودی بدون ردیف خرید (نوع «خرید»): {i['unclassified_in']}")

        sums = defaultdict(lambda: Decimal("0"))
        for row in StockMovement.objects.values("lot_id", "direction").annotate(q=Sum("qty")):
            sums[row["lot_id"]] += row["q"] if row["direction"] == "in" else -row["q"]
        bad = [l for l in StockLot.objects.select_related("item") if sums[l.pk] != l.qty_remaining]
        w(f"\n== لات‌های ناهم‌خوان با حرکت‌ها: {len(bad)} ==")
        for l in bad[:30]:
            w(f"لات {l.pk} | {l.item.name} | مانده‌ی ثبت‌شده {l.qty_remaining} | طبق حرکت‌ها {sums[l.pk]}")

        wrong = StockMovement.objects.exclude(movement_type__in=("in", "opening", "return")).filter(direction="in").exclude(movement_type="adjust")
        w(f"\n== حرکت با نوع و جهت ناسازگار (مثلاً out با جهت in): {wrong.count()} ==")

        lots = sorted(StockLot.objects.select_related("item").filter(qty_remaining__gt=0),
                      key=lambda l: l.qty_remaining * l.unit_cost, reverse=True)
        w("\n== ۱۰ لات با بیشترین ارزش ==")
        for l in lots[:10]:
            w(f"لات {l.pk} | {l.item.name} | {l.qty_remaining} × {l.unit_cost} = {l.qty_remaining * l.unit_cost}")

        w(f"\n== لات‌هایی با بهای واحد بالاتر از {opts['threshold']} ==")
        for l in [l for l in lots if l.unit_cost > opts["threshold"]][:30]:
            w(f"لات {l.pk} | {l.item.name} | بهای واحد {l.unit_cost}")
