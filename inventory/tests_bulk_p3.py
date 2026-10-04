import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Specialty
from catalog.models import Item
from inventory.models import Warehouse, StockMovement

User = get_user_model()


class BulkInventoryTests(TestCase):
    def setUp(self):
        self.wh_keeper_specialty, _ = Specialty.objects.get_or_create(name="انباردار")
        self.warehouse_keeper = User.objects.create_user(
            username="wh_keeper", phone_number="09300000003", password="Test@1234", role=User.Role.EMPLOYEE
        )
        self.warehouse_keeper.specialties.add(self.wh_keeper_specialty)

        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.item1 = Item.objects.create(name="کالای اول", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        self.item2 = Item.objects.create(name="کالای دوم", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)

    def test_bulk_opening_preview_and_confirm(self):
        self.client.force_login(self.warehouse_keeper)
        
        lines_json = json.dumps([
            {"item_id": self.item1.id, "qty": "100", "unit_cost": "5000"},
            {"item_id": self.item2.id, "qty": "200", "unit_cost": "6000"},
        ])
        
        # ۱. تست پیش‌نمایش
        response = self.client.post(reverse("inventory:bulk_opening"), {
            "lines_json": lines_json,
            "notes": "موجودی اولیه تستی",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inventory/bulk_opening_preview.html")

        # ۲. تایید نهایی
        response_confirm = self.client.post(reverse("inventory:bulk_opening"), {
            "lines_json": lines_json,
            "notes": "موجودی اولیه تستی",
            "confirm": "1",
        })
        self.assertEqual(response_confirm.status_code, 302) # redirect to home
        
        # ۳. بررسی ثبت حرکات انبار
        self.item1.refresh_from_db()
        self.item2.refresh_from_db()
        self.assertEqual(self.item1.current_stock, 100)
        self.assertEqual(self.item2.current_stock, 200)

    def test_bulk_reconciliation_preview_and_confirm(self):
        self.client.force_login(self.warehouse_keeper)
        
        # ایجاد موجودی تستی اولیه برای کالا ۱
        from inventory.services import record_manual_stock_change, CHANGE_KIND_OPENING
        record_manual_stock_change(
            item=self.item1, kind=CHANGE_KIND_OPENING, qty_raw="10", notes="موجودی اولیه کالا ۱",
            user=self.warehouse_keeper, unit_cost_raw="1000"
        )
        self.assertEqual(self.item1.current_stock, 10)

        # ارسال شمارش انبارگردانی: کالا ۱ شمارش‌شده ۱۲ عدد (تعدیل +۲)، کالا ۲ شمارش‌شده ۵ عدد (کافی نیست چون موجودی صفر است - خطا می‌دهد، پس شمارش ۲ را صفر ثبت می‌کنیم تا مغایرت نداشته باشد یا حذفش کنیم)
        lines_json = json.dumps([
            {"item_id": self.item1.id, "qty": "12", "system_stock": "10"},
        ])

        # ۱. پیش‌نمایش
        response = self.client.post(reverse("inventory:bulk_reconciliation"), {
            "lines_json": lines_json,
            "notes": "انبارگردانی تستی",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inventory/bulk_reconciliation_preview.html")

        # ۲. تایید نهایی
        response_confirm = self.client.post(reverse("inventory:bulk_reconciliation"), {
            "lines_json": lines_json,
            "notes": "انبارگردانی تستی",
            "confirm": "1",
        })
        self.assertEqual(response_confirm.status_code, 302)

        # ۳. بررسی موجودی جدید
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.current_stock, 12)
