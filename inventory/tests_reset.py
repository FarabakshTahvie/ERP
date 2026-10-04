from django.utils import timezone
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from catalog.models import Item
from inventory.models import StockMovement, Warehouse
from inventory.services import receive_stock


class ResetStockDataTests(TestCase):
    def test_reset_command_dry_run_and_execution(self):
        item = Item.objects.create(name="کالای تستی", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE, moving_average_cost=1000)
        wh = Warehouse.objects.create(name="انبار", is_default=True)
        receive_stock(item=item, warehouse=wh, qty=5, unit_cost=1000, received_at=timezone.now())

        self.assertEqual(StockMovement.objects.count(), 1)

        # بدون --yes پاک نمی‌کند
        with override_settings(DEBUG=True):
            call_command("reset_stock_data")
        self.assertEqual(StockMovement.objects.count(), 1)

        # با --yes و DEBUG=True (در تست DEBUG=False است، پس با override_settings یا force)
        with override_settings(DEBUG=True):
            call_command("reset_stock_data", yes=True)

        self.assertEqual(StockMovement.objects.count(), 0)
        item.refresh_from_db()
        self.assertEqual(item.moving_average_cost, 0)

    def test_debug_guard_and_force(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("reset_stock_data", yes=True)
            call_command("reset_stock_data", yes=True, force=True)
