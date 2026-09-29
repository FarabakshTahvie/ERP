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

    def test_create_item_success(self):
        item = create_item(
            name="لوله مسی ۱/۲",
            item_type=Item.ItemType.MATERIAL,
            unit=Item.Unit.METER,
            category_id=self.cat.id,
            reorder_point_raw="10",
            specs_pairs=[{"key": "برند", "value": "مهر تبریز"}]
        )
        self.assertTrue(item.is_active)
        self.assertEqual(item.name, "لوله مسی ۱/۲")
        self.assertEqual(item.specs, {"برند": "مهر تبریز"})
        self.assertEqual(item.reorder_point, Decimal("10.00"))

    def test_create_item_invalid_or_empty_type_or_unit(self):
        with self.assertRaises(ValueError):
            create_item(name="تست", item_type="invalid", unit=Item.Unit.METER)
        with self.assertRaises(ValueError):
            create_item(name="تست", item_type=Item.ItemType.MATERIAL, unit="invalid")

    def test_reorder_point_parsing(self):
        self.assertEqual(parse_nonneg_decimal("", label="تست"), Decimal("0.00"))
        self.assertEqual(parse_nonneg_decimal(None, label="تست"), Decimal("0.00"))
        self.assertEqual(parse_nonneg_decimal("۱۰٫۵", label="تست"), Decimal("10.50"))
        self.assertEqual(parse_nonneg_decimal("1,000.25", label="تست"), Decimal("1000.25"))
        with self.assertRaises(ValueError):
            parse_nonneg_decimal("-5", label="تست")
        with self.assertRaises(ValueError):
            parse_nonneg_decimal("متن‌خطا", label="تست")
        with self.assertRaises(ValueError):
            parse_nonneg_decimal("10000000000000", label="تست")

    def test_clean_specs(self):
        # ردیف خالی نادیده گرفته می‌شود
        pairs = [{"key": "", "value": ""}, {"key": "جنس", "value": "مس"}]
        self.assertEqual(clean_specs(pairs), {"جنس": "مس"})

        # نیمه‌پر خطا می‌دهد
        with self.assertRaises(ValueError):
            clean_specs([{"key": "جنس", "value": ""}])

        # برچسب تکراری خطا می‌دهد
        with self.assertRaises(ValueError):
            clean_specs([{"key": "جنس", "value": "مس"}, {"key": "جنس", "value": "آلومینیوم"}])

        # بیش از ۲۰ مورد خطا می‌دهد
        with self.assertRaises(ValueError):
            clean_specs([{"key": f"k{i}", "value": f"v{i}"} for i in range(25)])

        # غیر لیست خطا می‌دهد
        with self.assertRaises(ValueError):
            clean_specs("not-a-list")

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

    def test_resolve_category(self):
        # دسته‌ی جدید
        item1 = create_item(name="کالای الف", item_type=Item.ItemType.PART, unit=Item.Unit.PIECE, new_category_name="پمپ")
        self.assertEqual(item1.category.name, "پمپ")

        # استفاده از نام موجود با iexact
        item2 = create_item(name="کالای ب", item_type=Item.ItemType.PART, unit=Item.Unit.PIECE, new_category_name="  پمپ  ")
        self.assertEqual(item2.category_id, item1.category_id)

        # category_id نامعتبر
        with self.assertRaises(ValueError):
            create_item(name="کالای ج", item_type=Item.ItemType.PART, unit=Item.Unit.PIECE, category_id=999999)

    def test_update_item_specs_handling(self):
        item = create_item(name="تست مشخصات", item_type=Item.ItemType.CONSUMABLE, unit=Item.Unit.PIECE, specs_pairs=[{"key": "رنگ", "value": "آبی"}])
        # specs_pairs=None یعنی تغییر نکند
        update_item(item, name="تست مشخصات", specs_pairs=None)
        item.refresh_from_db()
        self.assertEqual(item.specs, {"رنگ": "آبی"})

        # specs_pairs=[] یعنی همه پاک شوند
        update_item(item, name="تست مشخصات", specs_pairs=[])
        item.refresh_from_db()
        self.assertEqual(item.specs, {})

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

    def test_update_item_locked_structure_with_none_type_and_unit(self):
        item = create_item(name="کالای قفل ۲", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=5, unit_cost=1000, received_at=timezone.now())
        # اگر در حالت قفل، type و unit برابر با None یا مقادیر قبلی ارسال شوند (مثل کنترل‌های disabled در فرم)
        updated = update_item(item, name="کالای قفل ۲", item_type=None, unit=None)
        self.assertEqual(updated.item_type, Item.ItemType.MATERIAL)
        self.assertEqual(updated.unit, Item.Unit.PIECE)

    def test_update_item_same_name_no_duplicate_error(self):
        item = create_item(name="کالای ثابت", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        # ویرایش با نام خودش بدون خطای تکراری
        updated = update_item(item, name="کالای ثابت", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        self.assertEqual(updated.name, "کالای ثابت")

    def test_set_item_active_false_with_stock_raises_value_error(self):
        item = create_item(name="کالای موجودی‌دار", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=self.warehouse, qty=2, unit_cost=1000, received_at=timezone.now())
        with self.assertRaises(ValueError):
            set_item_active(item, active=False)

    def test_set_item_active_transitions_zero_stock(self):
        item = create_item(name="کالای بدون موجودی", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        set_item_active(item, active=False)
        item.refresh_from_db()
        self.assertFalse(item.is_active)

        set_item_active(item, active=True)
        item.refresh_from_db()
        self.assertTrue(item.is_active)

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


class ItemViewAndTemplateTests(TestCase):
    def setUp(self):
        self.sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")
        self.warehouse_user = User.objects.create_user(
            username="wh_user_items", phone_number="09399990001",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        self.warehouse_user.specialties.add(self.sp_warehouse)

        self.other_tech = User.objects.create_user(
            username="wh_other_items", phone_number="09399990002",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )

        self.warehouse = Warehouse.objects.create(name="انبار مرکزی", is_default=True)
        self.active_item = create_item(name="کالای فعال", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        self.inactive_item = create_item(name="کالای غیرفعال", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        set_item_active(self.inactive_item, active=False)

    def test_item_views_permissions(self):
        client = Client()
        # تکنسین غیرانباردار -> 302
        client.force_login(self.other_tech)
        resp = client.get(reverse("inventory:item_new"))
        self.assertEqual(resp.status_code, 302)

        # انباردار -> 200
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("inventory:item_new"))
        self.assertEqual(resp.status_code, 200)

        resp = client.get(reverse("inventory:item_edit", args=[self.active_item.id]))
        self.assertEqual(resp.status_code, 200)

    def test_item_new_success_creates_item_and_redirects(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.post(reverse("inventory:item_new"), {
            "name": "کالای جدید وب",
            "item_type": Item.ItemType.PART,
            "unit": Item.Unit.PIECE,
            "reorder_point": "3",
            "specs_json": json.dumps([{"key": "مدل", "value": "2026"}])
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Item.objects.filter(name="کالای جدید وب").exists())

    def test_item_new_duplicate_name_warning_and_confirm(self):
        client = Client()
        client.force_login(self.warehouse_user)
        # تلاش برای ثبت نام تکراری بدون confirm_duplicate
        resp = client.post(reverse("inventory:item_new"), {
            "name": "کالای فعال",
            "item_type": Item.ItemType.MATERIAL,
            "unit": Item.Unit.PIECE,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn("duplicate_warning", resp.context)

        # تلاش مجدد با confirm_duplicate=1
        resp2 = client.post(reverse("inventory:item_new"), {
            "name": "کالای فعال",
            "item_type": Item.ItemType.MATERIAL,
            "unit": Item.Unit.PIECE,
            "confirm_duplicate": "1",
        })
        self.assertEqual(resp2.status_code, 302)

    def test_item_new_invalid_unit_renders_form_retaining_name(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.post(reverse("inventory:item_new"), {
            "name": "نام حفظ‌شونده",
            "item_type": Item.ItemType.MATERIAL,
            "unit": "invalid-unit",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["values"]["name"], "نام حفظ‌شونده")

    def test_item_edit_post_success_and_locked_item_disabled_selects(self):
        client = Client()
        client.force_login(self.warehouse_user)
        # ویرایش موفق
        resp = client.post(reverse("inventory:item_edit", args=[self.active_item.id]), {
            "name": "کالای فعال ویرایش‌شده",
            "item_type": Item.ItemType.MATERIAL,
            "unit": Item.Unit.PIECE,
            "reorder_point": "10",
        })
        self.assertEqual(resp.status_code, 302)
        self.active_item.refresh_from_db()
        self.assertEqual(self.active_item.name, "کالای فعال ویرایش‌شده")

        # کالای قفل شده دارای disabled در select نوع و واحد است
        receive_stock(item=self.active_item, warehouse=self.warehouse, qty=5, unit_cost=1000, received_at=timezone.now())
        resp_get = client.get(reverse("inventory:item_edit", args=[self.active_item.id]))
        self.assertContains(resp_get, "disabled")

    def test_item_toggle_active_get_405_post_toggle_and_stock_validation(self):
        client = Client()
        client.force_login(self.warehouse_user)
        # GET غیرمجاز است (require_POST)
        resp_get = client.get(reverse("inventory:item_toggle_active", args=[self.inactive_item.id]))
        self.assertEqual(resp_get.status_code, 405)

        # غیرفعال به فعال
        client.post(reverse("inventory:item_toggle_active", args=[self.inactive_item.id]))
        self.inactive_item.refresh_from_db()
        self.assertTrue(self.inactive_item.is_active)

        # فعال با موجودی > 0 غیرفعال نمی‌شود
        receive_stock(item=self.active_item, warehouse=self.warehouse, qty=3, unit_cost=1000, received_at=timezone.now())
        client.post(reverse("inventory:item_toggle_active", args=[self.active_item.id]))
        self.active_item.refresh_from_db()
        self.assertTrue(self.active_item.is_active)

    def test_item_quick_create_success(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.post(reverse("inventory:item_quick_create"), {
            "name": "کالای سریع",
            "item_type": Item.ItemType.PART,
            "unit": Item.Unit.PIECE,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["item"]["name"], "کالای سریع")

    def test_item_quick_create_validation_duplicate_and_unauthorized(self):
        client = Client()
        client.force_login(self.warehouse_user)
        # ورودی ناقص -> 400
        resp = client.post(reverse("inventory:item_quick_create"), {
            "name": "",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 400)

        # نام تکراری بدون confirm -> 409
        resp_dup = client.post(reverse("inventory:item_quick_create"), {
            "name": "کالای فعال",
            "item_type": Item.ItemType.MATERIAL,
            "unit": Item.Unit.PIECE,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp_dup.status_code, 409)
        self.assertTrue(resp_dup.json()["duplicate"])

        # کاربر غیرمجاز -> 302
        client.force_login(self.other_tech)
        resp_unauth = client.post(reverse("inventory:item_quick_create"), {
            "name": "تست",
        })
        self.assertEqual(resp_unauth.status_code, 302)

    def test_stock_table_inactive_items_sorting_links_and_filters(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("inventory:stock_table"))
        self.assertEqual(resp.status_code, 200)
        # لینک ردیف به item_edit است
        self.assertContains(resp, reverse("inventory:item_edit", args=[self.active_item.id]))

        # فیلتر غیرفعال‌ها st_f_active=0
        resp_inactive = client.get(reverse("inventory:stock_table") + "?st_f_active=0")
        self.assertEqual(resp_inactive.status_code, 200)

        # فیلتر فعال‌ها st_f_active=1
        resp_active = client.get(reverse("inventory:stock_table") + "?st_f_active=1")
        self.assertEqual(resp_active.status_code, 200)

    def test_stock_movement_form_excludes_inactive_items(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("inventory:stock_movement_new"))
        self.assertEqual(resp.status_code, 200)
        items_qs = resp.context["items"]
        self.assertIn(self.active_item, items_qs)
        self.assertNotIn(self.inactive_item, items_qs)

    def test_purchase_new_page_contains_picker_and_dialog_elements(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("inventory:purchase_new"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "item_picker.js")
        self.assertContains(resp, "open-quick-item")
        self.assertContains(resp, "quick-item-dialog")
        self.assertContains(resp, "unit")

    def test_technician_home_item_new_button_visibility(self):
        client = Client()
        # انباردار دکمه‌ی «کالای جدید» را دارد
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("home") + "?tab=stock")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("inventory:item_new"))

        # تکنسین معمولی ندارد
        client.force_login(self.other_tech)
        resp_tech = client.get(reverse("home"))
        self.assertEqual(resp_tech.status_code, 200)
        self.assertNotContains(resp_tech, reverse("inventory:item_new"))

    def test_static_item_picker_js_exists_and_contains_picker(self):
        path = finders.find("js/item_picker.js")
        self.assertIsNotNone(path)
        content = open(path, "r", encoding="utf-8").read()
        self.assertIn("fbItemPicker", content)
