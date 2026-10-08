from decimal import Decimal, InvalidOperation

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from catalog.models import MarginRule
from catalog.services import has_global_margin
from core.models import Specialty
from inventory.models import Warehouse

SPECIALTIES = ["بازدیدکننده", "کانال‌کش", "طراح اتوکد", "اپراتور CNC", "مونتاژکار",
               "پذیرش", "نصاب", "راننده", "انباردار", "حسابدار"]


class Command(BaseCommand):
    help = ("ساخت داده‌ی اولیه‌ی لازم (idempotent؛ داده‌ی موجود را خراب نمی‌کند): تخصص‌ها، طرف‌حساب داخلی، "
            "انبار پیش‌فرض، گردش‌کار v2 (پیش‌فرض)، سیاست‌های اطلاع‌رسانی و در صورت دادن --margin قانون سود سراسری.")

    def add_arguments(self, parser):
        parser.add_argument("--margin", default="", help="درصد سود سراسری؛ فقط اگر قانون سراسری فعالی نباشد ساخته می‌شود")

    def handle(self, *args, **opts):
        for name in SPECIALTIES:
            Specialty.objects.get_or_create(name=name)

        call_command("ensure_internal_party")

        if not Warehouse.objects.filter(is_default=True).exists():
            wh = Warehouse.objects.order_by("pk").first()
            if wh:
                wh.is_default = True
                wh.save(update_fields=["is_default"])
            else:
                Warehouse.objects.create(name="انبار مرکزی", is_default=True)

        call_command("setup_workflow_v2", make_default=True)
        call_command("setup_notification_policies", force=True)
        from messenger.services import ensure_main_group
        ensure_main_group()

        raw = (opts["margin"] or "").strip()
        if raw:
            try:
                pct = Decimal(raw)
            except InvalidOperation:
                raise CommandError("--margin باید عدد باشد.")
            if not (Decimal("0") <= pct <= Decimal("500")):
                raise CommandError("--margin باید بین ۰ و ۵۰۰ باشد.")
            if has_global_margin():
                self.stdout.write("قانون سود سراسری از قبل هست؛ دست نخورد.")
            else:
                MarginRule.objects.create(scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT,
                                          value=pct, valid_from=timezone.now())
                self.stdout.write(f"قانون سود سراسری {pct}٪ ساخته شد.")
        elif not has_global_margin():
            self.stdout.write(self.style.WARNING("قانون سود سراسری تعریف نشده؛ سود همه‌ی کالاها صفر حساب می‌شود."))
        self.stdout.write(self.style.SUCCESS("داده‌ی اولیه آماده است."))
