from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from core.models import Party
from catalog.models import Item
from inventory.models import Warehouse, StockLot, StockMovement
from inventory.services import receive_stock, consume_stock


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.supplier = Party.objects.create(
            name="تأمین‌کننده ورق",
            entity_type=Party.EntityType.COMPANY,
            company_registration_number="98765",
            is_supplier=True,
        )
        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.item = Item.objects.create(
            name="ورق گالوانیزه ۱.۲۵",
            item_type=Item.ItemType.MATERIAL,
            unit=Item.Unit.PIECE,
            reorder_point=5,
        )

    def test_receive_stock_and_moving_average(self):
        now = timezone.now()
        # ورود اول: ۵ عدد به قیمت ۱,۵۰۰,۰۰۰ تومان
        lot1 = receive_stock(
            item=self.item,
            warehouse=self.warehouse,
            qty=5,
            unit_cost=1500000,
            received_at=now,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, 5)
        self.assertEqual(self.item.moving_average_cost, Decimal('1500000.00'))

        # ورود دوم: ۵ عدد به قیمت ۱,۷۰۰,۰۰۰ تومان
        # میانگین = (5 * 1.5M + 5 * 1.7M) / 10 = 1,600,000
        lot2 = receive_stock(
            item=self.item,
            warehouse=self.warehouse,
            qty=5,
            unit_cost=1700000,
            received_at=now,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, 10)
        self.assertEqual(self.item.moving_average_cost, Decimal('1600000.00'))

        # ورود سوم: ۲ عدد به قیمت ۲,۰۰۰,۰۰۰ تومان
        # میانگین = (10 * 1.6M + 2 * 2M) / 12 = 20,000,000 / 12 = 1,666,666.67
        lot3 = receive_stock(
            item=self.item,
            warehouse=self.warehouse,
            qty=2,
            unit_cost=2000000,
            received_at=now,
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, 12)
        self.assertAlmostEqual(float(self.item.moving_average_cost), 1666666.67, places=1)

    def test_fifo_consumption(self):
        t1 = timezone.now() - timezone.timedelta(days=2)
        t2 = timezone.now() - timezone.timedelta(days=1)

        lot1 = receive_stock(item=self.item, warehouse=self.warehouse, qty=4, unit_cost=1000, received_at=t1)
        lot2 = receive_stock(item=self.item, warehouse=self.warehouse, qty=6, unit_cost=2000, received_at=t2)

        # مصرف ۵ عدد: باید ۴ عدد از لات اول و ۱ عدد از لات دوم مصرف شود
        breakdown = consume_stock(item=self.item, qty=5)
        lot1.refresh_from_db()
        lot2.refresh_from_db()

        self.assertEqual(lot1.qty_remaining, 0)
        self.assertEqual(lot2.qty_remaining, 5)
        self.assertEqual(len(breakdown), 2)
        self.assertEqual(breakdown[0][1], 4)
        self.assertEqual(breakdown[1][1], 1)

    def test_insufficient_stock_raises_error(self):
        receive_stock(item=self.item, warehouse=self.warehouse, qty=2, unit_cost=1000, received_at=timezone.now())
        with self.assertRaises(ValueError):
            consume_stock(item=self.item, qty=5)
