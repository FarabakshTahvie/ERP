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

    def test_stock_table_view_permissions(self):
        client = Client()
        url = reverse("inventory:stock_table")

        client.force_login(self.other_tech)
        resp = client.get(url)
        self.assertEqual(resp.status_code, 302)  # user_passes_test به لاگین ریدایرکت می‌کند

        client.force_login(self.warehouse_user)
        resp2 = client.get(url)
        self.assertEqual(resp2.status_code, 200)

    def test_stock_table_shows_low_stock_badge_and_ordering(self):
        item_low = Item.objects.create(
            name="آ - کالای کم", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=10,
        )
        receive_stock(item=item_low, warehouse=self.warehouse, qty=2, unit_cost=1000, received_at=timezone.now())
        item_high = Item.objects.create(
            name="ب - کالای زیاد", item_type=Item.ItemType.MATERIAL,
            category=self.cat, unit=Item.Unit.PIECE, reorder_point=10,
        )
        receive_stock(item=item_high, warehouse=self.warehouse, qty=100, unit_cost=1000, received_at=timezone.now())

        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("inventory:stock_table"))
        content = resp.content.decode("utf-8")
        self.assertIn("کمبود", content)
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

    def test_clean_purchase_lines_rejects_zero_and_inactive(self):
        with self.assertRaises(ValueError):
            _clean_purchase_lines([{"id": self.item1.id, "qty": "0", "unit_cost": "1000"}])
        with self.assertRaises(ValueError):
            _clean_purchase_lines([{"id": self.item1.id, "qty": "1", "unit_cost": "0"}])
        with self.assertRaises(ValueError):
            _clean_purchase_lines([{"id": self.item_inactive.id, "qty": "1", "unit_cost": "1000"}])
        ok = _clean_purchase_lines([{"id": self.item1.id, "qty": "2.5", "unit_cost": "1000"}])
        self.assertEqual(ok[0]["qty"], Decimal("2.5"))

    def test_resolve_supplier_party_creates_with_is_supplier_true(self):
        party = _resolve_supplier_party(party_data={
            "name": "تامین‌کننده جدید", "phone_number": "09350000002",
            "entity_type": "individual", "national_code": "2222222222",
        })
        self.assertTrue(party.is_supplier)

    def test_resolve_supplier_party_rejects_duplicate_phone(self):
        with self.assertRaises(ValueError):
            _resolve_supplier_party(party_data={
                "name": "تکراری", "phone_number": self.supplier.phone_number,
                "entity_type": "individual", "national_code": "3333333333",
            })

    def test_validate_invoice_file_extension_and_size(self):
        bad = SimpleUploadedFile("bad.exe", b"x", content_type="application/octet-stream")
        with self.assertRaises(ValueError):
            _validate_invoice_file(bad)
        big = SimpleUploadedFile("big.jpg", b"x" * (11 * 1024 * 1024), content_type="image/jpeg")
        with self.assertRaises(ValueError):
            _validate_invoice_file(big)

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

    def test_purchase_new_view_permissions_and_flow(self):
        sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")
        wh_user = User.objects.create_user(
            username="pv_wh", phone_number="09350000003",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        wh_user.specialties.add(sp_warehouse)
        other = User.objects.create_user(
            username="pv_other", phone_number="09350000004",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )

        client = Client()
        client.force_login(other)
        self.assertEqual(client.get(reverse("inventory:purchase_new")).status_code, 302)

        client.force_login(wh_user)
        self.assertEqual(client.get(reverse("inventory:purchase_new")).status_code, 200)

        resp = client.post(reverse("inventory:purchase_new"), {
            "supplier_party_id": str(self.supplier.id),
            "purchased_at": "",
            "invoice_number": "INV-002",
            "lines_json": json.dumps([{"id": self.item1.id, "qty": "3", "unit_cost": "20000"}]),
        })
        self.assertRedirects(resp, reverse("home"))
        self.assertEqual(Purchase.objects.filter(invoice_number="INV-002").count(), 1)


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

    def test_parse_decimal_input_accepts_persian_digits_and_rejects_invalid(self):
        self.assertEqual(parse_decimal_input("۱۰.۵"), Decimal("10.5"))
        with self.assertRaises(ValueError):
            parse_decimal_input("abc")
        with self.assertRaises(ValueError):
            parse_decimal_input("0")
        with self.assertRaises(ValueError):
            parse_decimal_input("-5")

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
        record_manual_stock_change(item=item, kind=CHANGE_KIND_CONSUME, qty_raw="4", notes="مصرف در پروژه تست", user=self.user)
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

    def test_receive_stock_backward_compatible_without_notes(self):
        """رگرسیون: خرید عادی (W2) نباید عوض شود."""
        item = Item.objects.create(name="کالای تست ۹", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=1, unit_cost=500, received_at=timezone.now())
        movement = StockMovement.objects.filter(item=item, movement_type=StockMovement.MovementType.IN).latest("created_at")
        self.assertEqual(movement.notes, "")
        self.assertIsNone(movement.created_by)

    def test_stock_movement_view_permissions_and_flow(self):
        sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")
        wh_user = User.objects.create_user(
            username="mv_wh", phone_number="09360000002",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        wh_user.specialties.add(sp_warehouse)
        item = Item.objects.create(name="کالای تست ۱۰", item_type=Item.ItemType.MATERIAL, category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=10, unit_cost=1000, received_at=timezone.now())

        client = Client()
        client.force_login(self.user)  # بدون تخصص انباردار
        self.assertEqual(client.get(reverse("inventory:stock_movement_new")).status_code, 302)

        client.force_login(wh_user)
        self.assertEqual(client.get(reverse("inventory:stock_movement_new")).status_code, 200)

        resp = client.post(reverse("inventory:stock_movement_new"), {
            "item_id": item.id, "kind": CHANGE_KIND_CONSUME, "qty": "2", "notes": "تست از ویو",
        })
        self.assertRedirects(resp, reverse("home"))
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("8"))



