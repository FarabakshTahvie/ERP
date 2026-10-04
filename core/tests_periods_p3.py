import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Specialty
from catalog.models import Item
from inventory.models import Warehouse, StockMovement
from core.models import PeriodLock

User = get_user_model()


class PeriodLockTests(TestCase):
    def setUp(self):
        self.wh_keeper_specialty, _ = Specialty.objects.get_or_create(name="انباردار")
        self.accountant_specialty, _ = Specialty.objects.get_or_create(name="حسابدار")
        
        # کاربران
        self.manager = User.objects.create_user(
            username="manager", phone_number="09300000001", password="Test@1234", role=User.Role.ADMIN
        )
        self.accountant = User.objects.create_user(
            username="accountant", phone_number="09300000002", password="Test@1234", role=User.Role.EMPLOYEE
        )
        self.accountant.specialties.add(self.accountant_specialty)
        
        self.warehouse_keeper = User.objects.create_user(
            username="wh_keeper", phone_number="09300000003", password="Test@1234", role=User.Role.EMPLOYEE
        )
        self.warehouse_keeper.specialties.add(self.wh_keeper_specialty)

        # انبار و کالا
        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.item = Item.objects.create(
            name="کالای تستی", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE
        )

    def test_period_lock_blocks_stock_transactions(self):
        # بستن ماه گذشته (سال ۱۴۰۵، ماه ۷ مهرماه)
        PeriodLock.objects.create(year=1405, month=7, is_locked=True)

        # تلاش برای ثبت تراکنش انبار با تاریخ داخل ماه بسته
        import jdatetime
        target_date = jdatetime.date(1405, 7, 15).togregorian()

        from inventory.services import record_manual_stock_change, CHANGE_KIND_OPENING
        with self.assertRaises(ValueError) as ctx:
            record_manual_stock_change(
                item=self.item,
                kind=CHANGE_KIND_OPENING,
                qty_raw="10",
                notes="تست",
                user=self.warehouse_keeper,
                unit_cost_raw="1000",
                movement_date=target_date,
            )
        self.assertIn("بسته شده است", str(ctx.exception))
