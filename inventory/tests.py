from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from core.models import Party, Specialty
from catalog.models import Item, ItemCategory
from inventory.models import Warehouse, StockLot, StockMovement
from inventory.services import receive_stock, consume_stock, user_can_manage_inventory, low_stock_items_count

User = get_user_model()


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


class WarehouseAccessAndStockViewTests(TestCase):
    def setUp(self):
        self.sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")
        self.warehouse_user = User.objects.create_user(
            username="wh_user", phone_number="09300000101",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        self.warehouse_user.specialties.add(self.sp_warehouse)

        self.other_tech = User.objects.create_user(
            username="wh_other", phone_number="09300000102",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )

        self.manager = User.objects.create_user(
            username="wh_manager", phone_number="09300000103",
            password="Test@1234", role=User.Role.ADMIN, is_superuser=True,
        )

        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.cat = ItemCategory.objects.create(name="دسته تست انبار")

    def test_user_can_manage_inventory(self):
        self.assertTrue(user_can_manage_inventory(self.warehouse_user))
        self.assertFalse(user_can_manage_inventory(self.other_tech))
        self.assertFalse(user_can_manage_inventory(self.manager))  # مدیر استثنا نیست؛ از پنل ادمین استفاده می‌کند

    def test_low_stock_count_ignores_zero_reorder_point_and_inactive(self):
        # کالای بدون حد هشدار: هرگز کمبود حساب نمی‌شود، حتی با موجودی صفر
        Item.objects.create(
            name="کالای بدون آستانه", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=0,
        )
        # کالای فعال با آستانه، بدون هیچ خرید (بدون لات) => باید کمبود حساب شود
        Item.objects.create(
            name="کالای بدون خرید", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=5,
        )
        # کالای غیرفعال با آستانه و موجودی صفر: نباید حساب شود
        Item.objects.create(
            name="کالای غیرفعال", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=5, is_active=False,
        )
        # کالای با موجودی کافی: نباید حساب شود
        item_ok = Item.objects.create(
            name="کالای کافی", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=5,
        )
        receive_stock(item=item_ok, warehouse=self.warehouse, qty=20, unit_cost=1000, received_at=timezone.now())

        self.assertEqual(low_stock_items_count(), 1)  # فقط «کالای بدون خرید»


import json
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import Party
from inventory.models import Purchase, PurchaseLine
from inventory.services import (
    create_purchase_from_form, _clean_purchase_lines, _resolve_supplier_party, _validate_invoice_file,
)


class PurchaseEntryTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.cat = ItemCategory.objects.create(name="دسته تست خرید")
        self.item1 = Item.objects.create(
            name="کالای خرید ۱", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE,
        )
        self.item_inactive = Item.objects.create(
            name="کالای غیرفعال", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, is_active=False,
        )
        self.supplier = Party.objects.create(
            name="تامین‌کننده تست", phone_number="09350000001",
            entity_type=Party.EntityType.INDIVIDUAL, national_code="1111111111", is_supplier=True,
        )



    def test_resolve_supplier_party_creates_with_is_supplier_true(self):
        party = _resolve_supplier_party(party_data={
            "name": "تامین‌کننده جدید", "phone_number": "09350000002",
            "entity_type": "individual", "national_code": "2222222222",
        })
        self.assertTrue(party.is_supplier)

    def test_resolve_supplier_party_adds_supplier_role_to_existing_party_without_it(self):
        existing_client = Party.objects.create(
            name="کارفرمای موجود", phone_number="09350000005",
            entity_type=Party.EntityType.INDIVIDUAL, national_code="4444444444", is_client=True,
        )
        self.assertFalse(existing_client.is_supplier)
        resolved = _resolve_supplier_party(party_id=existing_client.id)
        self.assertTrue(resolved.is_supplier)
        existing_client.refresh_from_db()
        self.assertTrue(existing_client.is_supplier)

    def test_resolve_supplier_party_rejects_duplicate_phone(self):
        with self.assertRaises(ValueError):
            _resolve_supplier_party(party_data={
                "name": "تکراری", "phone_number": self.supplier.phone_number,
                "entity_type": "individual", "national_code": "3333333333",
            })



    def test_create_purchase_from_form_success_updates_stock(self):
        create_purchase_from_form(
            supplier_party_id=self.supplier.id,
            purchased_at=timezone.now(),
            invoice_number="INV-001",
            lines_raw=[{"id": self.item1.id, "qty": "10", "unit_cost": "50000"}],
        )
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(PurchaseLine.objects.count(), 1)
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.current_stock, Decimal("10"))
        self.assertEqual(self.item1.moving_average_cost, Decimal("50000"))

    def test_create_purchase_without_default_warehouse_fails(self):
        self.warehouse.is_default = False
        self.warehouse.save()
        with self.assertRaises(ValueError) as ctx:
            create_purchase_from_form(
                supplier_party_id=self.supplier.id,
                purchased_at=timezone.now(),
                lines_raw=[{"id": self.item1.id, "qty": "1", "unit_cost": "1000"}],
            )
        self.assertIn("انبار پیش‌فرض", str(ctx.exception))

    def test_invalid_line_rolls_back_whole_purchase(self):
        with self.assertRaises(ValueError):
            create_purchase_from_form(
                supplier_party_id=self.supplier.id,
                purchased_at=timezone.now(),
                lines_raw=[
                    {"id": self.item1.id, "qty": "5", "unit_cost": "1000"},
                    {"id": self.item1.id, "qty": "0", "unit_cost": "1000"},  # ردیف خراب
                ],
            )
        self.assertEqual(Purchase.objects.count(), 0)  # هیچ‌چیزی نباید ساخته شده باشد




from inventory.services import (
    parse_decimal_input, record_manual_stock_change,
    CHANGE_KIND_CONSUME, CHANGE_KIND_ADJUST_DECREASE, CHANGE_KIND_ADJUST_INCREASE,
)
from inventory.models import StockMovement


class ManualStockChangeTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.cat = ItemCategory.objects.create(name="دسته تست تعدیل")
        self.user = User.objects.create_user(
            username="mv_user", phone_number="09360000001",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )



    def test_notes_always_required(self):
        item = Item.objects.create(name="کالای تست ۱", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        with self.assertRaises(ValueError) as ctx:
            record_manual_stock_change(item=item, kind=CHANGE_KIND_CONSUME, qty_raw="1", notes="", user=self.user)
        self.assertIn("دلیل", str(ctx.exception))

    def test_invalid_kind_rejected(self):
        item = Item.objects.create(name="کالای تست ۲", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        with self.assertRaises(ValueError):
            record_manual_stock_change(item=item, kind="something_else", qty_raw="1", notes="دلیل", user=self.user)

    def test_consume_reduces_stock_with_out_movement(self):
        item = Item.objects.create(name="کالای تست ۳", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=10, unit_cost=1000, received_at=timezone.now())
        record_manual_stock_change(item=item, kind=CHANGE_KIND_CONSUME, qty_raw="4", notes="مصرف در پروژه تست", user=self.user, internal=True)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("6"))
        movement = StockMovement.objects.filter(item=item, movement_type=StockMovement.MovementType.OUT).latest("created_at")
        self.assertEqual(movement.notes, "مصرف در پروژه تست")
        self.assertEqual(movement.created_by, self.user)

    def test_adjust_decrease_uses_adjust_movement_type(self):
        item = Item.objects.create(name="کالای تست ۴", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=10, unit_cost=1000, received_at=timezone.now())
        record_manual_stock_change(item=item, kind=CHANGE_KIND_ADJUST_DECREASE, qty_raw="3", notes="کسری انبارگردانی", user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("7"))
        self.assertTrue(StockMovement.objects.filter(item=item, movement_type=StockMovement.MovementType.ADJUST, qty=3).exists())
        self.assertFalse(StockMovement.objects.filter(item=item, movement_type=StockMovement.MovementType.OUT).exists())

    def test_adjust_decrease_insufficient_stock_raises(self):
        item = Item.objects.create(name="کالای تست ۵", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=2, unit_cost=1000, received_at=timezone.now())
        with self.assertRaises(ValueError) as ctx:
            record_manual_stock_change(item=item, kind=CHANGE_KIND_ADJUST_DECREASE, qty_raw="5", notes="کسری", user=self.user)
        self.assertIn("کافی نیست", str(ctx.exception))

    def test_adjust_increase_creates_new_lot_with_notes_and_updates_average(self):
        item = Item.objects.create(name="کالای تست ۶", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=10, unit_cost=1000, received_at=timezone.now())
        record_manual_stock_change(
            item=item, kind=CHANGE_KIND_ADJUST_INCREASE, qty_raw="10",
            unit_cost_raw="2000", notes="کشف موجودی جا افتاده در انبارگردانی", user=self.user,
        )
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("20"))
        self.assertEqual(item.moving_average_cost, Decimal("1500"))  # (10*1000+10*2000)/20
        movement = StockMovement.objects.filter(item=item, movement_type=StockMovement.MovementType.ADJUST, qty=10).latest("created_at")
        self.assertEqual(movement.notes, "کشف موجودی جا افتاده در انبارگردانی")
        self.assertEqual(movement.created_by, self.user)

    def test_adjust_increase_defaults_unit_cost_to_moving_average(self):
        item = Item.objects.create(name="کالای تست ۷", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=5, unit_cost=3000, received_at=timezone.now())
        record_manual_stock_change(item=item, kind=CHANGE_KIND_ADJUST_INCREASE, qty_raw="5", notes="کشف موجودی", user=self.user)
        item.refresh_from_db()
        self.assertEqual(item.moving_average_cost, Decimal("3000"))

    def test_adjust_increase_without_history_requires_manual_cost(self):
        item = Item.objects.create(name="کالای تست ۸", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        with self.assertRaises(ValueError) as ctx:
            record_manual_stock_change(item=item, kind=CHANGE_KIND_ADJUST_INCREASE, qty_raw="5", notes="کشف موجودی", user=self.user)
        self.assertIn("بهای واحد را دستی وارد کنید", str(ctx.exception))






