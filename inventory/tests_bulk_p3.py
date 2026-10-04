from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item
from core.models import Specialty
from inventory import bulk
from inventory.models import StockMovement, Warehouse
from inventory.services import receive_stock

MT, DIR = StockMovement.MovementType, StockMovement.Direction


class BulkBase(TestCase):
    def setUp(self):
        self.keeper = User.objects.create_user(username="bk_keeper", password="pw", role=User.Role.EMPLOYEE)
        self.keeper.specialties.add(Specialty.objects.get_or_create(name="انباردار")[0])
        self.other = User.objects.create_user(username="bk_other", password="pw", role=User.Role.EMPLOYEE)
        self.wh = Warehouse.objects.create(name="انبار", is_default=True)
        mk = lambda n, **kw: Item.objects.create(name=n, item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE, **kw)
        self.i1, self.i2 = mk("کالای اول"), mk("ورق گالوانیزه")
        self.off = mk("کالای غیرفعال", is_active=False)
        self.client.force_login(self.keeper)

    def stock(self, item):
        return Item.objects.get(pk=item.pk).current_stock

    def post(self, mode, text, *, action="preview", notes="سند آزمایشی", **extra):
        url = reverse("inventory:bulk_opening" if mode == "opening" else "inventory:bulk_reconciliation")
        return self.client.post(url, {"pasted": text, "notes": notes, "action": action, **extra})

    def confirm(self, mode, text, **extra):
        digest = self.post(mode, text).context["digest"]
        return self.post(mode, text, action="confirm", digest=digest, **extra)


class BulkPasteOpeningTests(BulkBase):
    def test_preview_then_confirm_records_opening_movements(self):
        text = "کالای اول\t۱۰۰\t5,000\nورق گالوانیزه\t200\t6000"
        r = self.post("opening", text)
        self.assertEqual(len(r.context["preview"]["lines"]), 2)
        self.assertEqual(self.stock(self.i1), 0)           # پیش‌نمایش چیزی ننوشته
        self.assertEqual(self.confirm("opening", text).status_code, 302)
        self.assertEqual((self.stock(self.i1), self.stock(self.i2)), (Decimal("100"), Decimal("200")))
        self.assertEqual(Item.objects.get(pk=self.i1.pk).moving_average_cost, Decimal("5000"))
        mv = StockMovement.objects.get(item=self.i1)
        self.assertEqual((mv.movement_type, mv.direction), (MT.OPENING, DIR.IN))
        self.assertTrue(mv.notes.startswith("ورود گروهی موجودی اولیه"))

    def test_header_row_arabic_letters_and_inactive_items(self):
        text = "نام کالا\tمقدار\tبهای واحد (تومان)\tواحد\nورق گالوانيزه\t1\t1000\tعدد"
        self.assertEqual(self.confirm("opening", text).status_code, 302)
        self.assertEqual(self.stock(self.i2), Decimal("1"))
        r = self.post("opening", "کالای غیرفعال\t1\t1000")
        self.assertEqual(r.context["preview"]["error_count"], 1)

    def test_unmatched_duplicate_and_bad_numbers_block_everything(self):
        text = "کالای اول\t1\t1000\nناشناخته\t1\t1000\nکالای اول\t2\t1000\nورق گالوانیزه\tabc\t5"
        r = self.post("opening", text)
        self.assertEqual(r.context["preview"]["error_count"], 3)
        self.confirm("opening", text)
        self.assertEqual((self.stock(self.i1), self.stock(self.i2)), (0, 0))

    def test_absolute_price_guard_needs_ack(self):
        text = "کالای اول\t1\t60,000,000"
        self.assertEqual(self.post("opening", text).context["preview"]["warning_count"], 1)
        self.confirm("opening", text)
        self.assertEqual(self.stock(self.i1), 0)
        self.confirm("opening", text, ack="1")
        self.assertEqual(self.stock(self.i1), Decimal("1"))

    def test_ratio_guard_against_current_average_and_existing_stock(self):
        receive_stock(item=self.i1, warehouse=self.wh, qty=5, unit_cost=1000, received_at=timezone.now())
        w = self.post("opening", "کالای اول\t1\t10000").context["preview"]["lines"][0]["warnings"]
        self.assertEqual(len(w), 2)    # موجودی قبلی + ۱۰ برابر میانگین
        self.confirm("opening", "کالای اول\t1\t1100")
        self.assertEqual(self.stock(self.i1), 5)   # هنوز بدون ack نرفته (هشدار موجودی قبلی)

    def test_changed_text_after_preview_is_rejected(self):
        digest = self.post("opening", "کالای اول\t1\t1000").context["digest"]
        self.post("opening", "کالای اول\t9\t1000", action="confirm", digest=digest)
        self.assertEqual(self.stock(self.i1), 0)

    def test_more_than_limit_rows_rejected(self):
        r = self.post("opening", "\n".join("کالای اول\t1\t1000" for _ in range(bulk.MAX_BULK_ROWS + 1)))
        self.assertIsNone(r.context["preview"])

    def test_commit_is_all_or_nothing(self):
        text = "کالای اول\t10\t1000\nورق گالوانیزه\t5\t2000"
        real, calls = bulk.record_manual_stock_change, {"n": 0}

        def flaky(**kw):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("boom")
            return real(**kw)

        with mock.patch("inventory.bulk.record_manual_stock_change", flaky):
            with self.assertRaises(ValueError):
                bulk.commit("opening", text, "سند", self.keeper, acknowledged=False)
        self.assertEqual((self.stock(self.i1), self.stock(self.i2)), (0, 0))


class BulkPasteCountTests(BulkBase):
    def setUp(self):
        super().setUp()
        receive_stock(item=self.i1, warehouse=self.wh, qty=10, unit_cost=1000, received_at=timezone.now())
        receive_stock(item=self.i2, warehouse=self.wh, qty=5, unit_cost=2000, received_at=timezone.now())

    def test_difference_recorded_as_adjust_in_both_directions(self):
        self.assertEqual(self.confirm("count", "کالای اول\t12\nورق گالوانیزه\t3").status_code, 302)
        self.assertEqual((self.stock(self.i1), self.stock(self.i2)), (Decimal("12"), Decimal("3")))
        self.assertTrue(StockMovement.objects.filter(item=self.i1, movement_type=MT.ADJUST, direction=DIR.IN, qty=2).exists())
        self.assertTrue(StockMovement.objects.filter(item=self.i2, movement_type=MT.ADJUST, direction=DIR.OUT, qty=2).exists())

    def test_blank_and_equal_rows_are_skipped_and_nothing_to_do_is_reported(self):
        r = self.post("count", "کالای اول\t\nورق گالوانیزه\t5")
        self.assertIsNone(r.context["preview"])

    def test_zero_count_warns_and_needs_ack(self):
        text = "کالای اول\t0"
        self.assertEqual(self.post("count", text).context["preview"]["warning_count"], 1)
        self.confirm("count", text)
        self.assertEqual(self.stock(self.i1), 10)
        self.confirm("count", text, ack="1")
        self.assertEqual(self.stock(self.i1), 0)

    def test_increase_without_average_cost_is_an_error(self):
        Item.objects.create(name="کالای بدون بها", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        self.assertEqual(self.post("count", "کالای بدون بها\t3").context["preview"]["error_count"], 1)


class BulkAccessAndTemplateTests(BulkBase):
    def test_only_inventory_users(self):
        self.client.force_login(self.other)
        for name in ("inventory:bulk_opening", "inventory:bulk_reconciliation"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.assertEqual(self.client.get(reverse("inventory:bulk_template", args=["opening"])).status_code, 302)

    def test_template_download_has_bom_and_only_active_items(self):
        resp = self.client.get(reverse("inventory:bulk_template", args=["opening"]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        self.assertIn("کالای اول", body)
        self.assertNotIn("کالای غیرفعال", body)
        self.assertEqual(self.client.get(reverse("inventory:bulk_template", args=["x"])).status_code, 404)
