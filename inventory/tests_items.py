from decimal import Decimal
import json
from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.staticfiles import finders
from core.models import Party, Specialty
from catalog.models import Item, ItemCategory
from inventory.models import Warehouse, StockLot, StockMovement, Purchase
from inventory.services import (
    create_item, update_item, set_item_active, item_structure_locked,
    parse_nonneg_decimal, clean_specs, DuplicateItemNameError, receive_stock,
    create_purchase_from_form, user_can_manage_inventory
)

User = get_user_model()


class ItemServiceTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.cat = ItemCategory.objects.create(name="لوله و اتصالات")

    def test_duplicate_name_detection_and_confirmation(self):
        create_item(name="ورق گالوانیزه ۱", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)

        # نام مشابه با «ي» / «ك» یا فاصله اضافی
        with self.assertRaises(DuplicateItemNameError):
            create_item(name="ورق گالوانيزه ۱", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE, confirm_duplicate=False)

        # با تأیید صریح موفق می‌شود
        item2 = create_item(
            name="ورق گالوانيزه ۱", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE, confirm_duplicate=True
        )
        self.assertEqual(item2.name, "ورق گالوانيزه ۱")

    def test_update_item_locked_structure_after_receive_stock(self):
        item = create_item(name="کالای قفل", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.METER)
        receive_stock(item=item, warehouse=self.warehouse, qty=10, unit_cost=5000, received_at=timezone.now())
        self.assertTrue(item_structure_locked(item))

        # تغییر نوع یا واحد خطا می‌دهد
        with self.assertRaises(ValueError):
            update_item(item, name="کالای قفل", item_type=Item.ItemType.CONSUMABLE, unit=Item.Unit.METER)

        # تغییر نام یا دسته مجاز است
        updated = update_item(item, name="کالای قفل ویرایش‌شده", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.METER)
        self.assertEqual(updated.name, "کالای قفل ویرایش‌شده")

    def test_set_item_active_false_with_stock_raises_value_error(self):
        item = create_item(name="کالای موجودی‌دار", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=2, unit_cost=1000, received_at=timezone.now())
        with self.assertRaises(ValueError):
            set_item_active(item, active=False)

    def test_create_purchase_from_form_with_inactive_item_fails(self):
        item = create_item(name="کالای غیرفعال خرید", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        set_item_active(item, active=False)
        supplier = Party.objects.create(name="تأمین‌کننده تست", phone_number="09121112233", is_supplier=True)
        lines_raw = [{"item_id": item.id, "qty": "5", "unit_cost": "1000"}]
        with self.assertRaises(ValueError):
            create_purchase_from_form(
                supplier_party_id=supplier.id,
                purchased_at=timezone.now(),
                lines_raw=lines_raw,
            )
        self.assertEqual(Purchase.objects.count(), 0)



