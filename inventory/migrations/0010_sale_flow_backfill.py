from decimal import Decimal, ROUND_HALF_UP

import jdatetime
from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    Sale = apps.get_model("inventory", "Sale")
    SaleLine = apps.get_model("inventory", "SaleLine")
    Warehouse = apps.get_model("inventory", "Warehouse")
    for line in SaleLine.objects.all():
        line.total = (line.qty * line.unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        line.save(update_fields=["total"])
    sales = list(Sale.objects.order_by("sold_at", "pk"))
    if not sales:
        return
    warehouse = (Warehouse.objects.filter(is_default=True).first()
                 or Warehouse.objects.order_by("pk").first()
                 or Warehouse.objects.create(name="انبار مرکزی", is_default=True))
    counters = {}
    for sale in sales:
        j = jdatetime.date.fromgregorian(date=timezone.localtime(sale.sold_at).date())
        prefix = f"S{j.year % 100:02d}{j.month:02d}-"
        counters[prefix] = counters.get(prefix, 0) + 1
        sale.number = f"{prefix}{counters[prefix]:02d}"
        sale.warehouse = warehouse
        sale.status = "delivered"            # فروش‌های قبلی همان لحظه از انبار کم شده بودند
        sale.delivered_at = sale.sold_at
        sale.delivered_by_id = sale.created_by_id
        sale.save(update_fields=["number", "warehouse", "status", "delivered_at", "delivered_by"])


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0009_sale_flow'),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
