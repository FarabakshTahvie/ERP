import json
from decimal import Decimal

from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from accounts.models import User
from catalog.models import Item, Service, ServiceBOM
from core.models import Party
from finance import accounting
from finance.models import Invoice
from finance.services import build_invoice_lines, generate_invoice_for_project
from inventory.models import StockMovement
from projects import proforma_rows as rows
from projects.models import (
    Project, ProjectServiceMaterial, ProjectStage, StageKind, StageUsage, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.usage import set_usage, usage_context
from utils.test_helpers import make_accountant


def svc_row(service, materials, qty="1", price="1000000", pk=None):
    """materials: [(item, on), ...] ← رشته‌ی JSON یک‌ردیفی مثل ارسال مرورگر"""
    d = {"service_id": service.pk, "qty": qty, "unit_price": price,
         "materials": [{"item_id": i.pk, "on": on} for i, on in materials]}
    if pk:
        d["pk"] = pk
    return rows.parse_service_row(json.dumps([d]))


class DefaultItemsBase(TestCase):
    def setUp(self):
        self.acc = make_accountant("di_acc")
        self.tech = User.objects.create_user(username="di_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری کالاهای پیش‌فرض", is_client=True, is_partner=True,
                                          phone_number="09128880001")
        self.project = Project.objects.create(name="پروژه کالاهای پیش‌فرض", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        mk = lambda n, t, u, **kw: Item.objects.create(name=n, item_type=t, unit=u, **kw)
        self.sheet = mk("ورق تست پیش‌فرض", Item.ItemType.MATERIAL, Item.Unit.SQUARE_METER)
        self.flange = mk("فلنج تست پیش‌فرض", Item.ItemType.PART, Item.Unit.PIECE)
        self.channel = mk("کانال تست پیش‌فرض", Item.ItemType.MANUFACTURED, Item.Unit.METER)
        self.dead = mk("کالای غیرفعال پیش‌فرض", Item.ItemType.PART, Item.Unit.PIECE, is_active=False)
        self.service = Service.objects.create(name="خدمت تست پیش‌فرض")
        for it in (self.sheet, self.channel, self.dead):
            ServiceBOM.objects.create(service=self.service, item=it)

    def save(self, materials, **kw):
        return rows.save_service_line(project=self.project, actor=self.acc,
                                      row=svc_row(self.service, materials, **kw))

    def saved_items(self, line):
        return set(line.materials.values_list("item_id", flat=True))


class DefaultItemsCatalogTests(TestCase):
    def test_default_item_has_only_service_and_item(self):
        s = Service.objects.create(name="سرویس آزمایشی کاتالوگ")
        i = Item.objects.create(name="کالای آزمایشی کاتالوگ", item_type=Item.ItemType.PART, unit=Item.Unit.PIECE)
        bom = ServiceBOM.objects.create(service=s, item=i)
        fields = {f.name for f in ServiceBOM._meta.get_fields()}
        self.assertEqual(fields, {"id", "service", "item"})
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ServiceBOM.objects.create(service=s, item=i)

    def test_project_material_has_only_service_line_and_item(self):
        fields = {f.name for f in ProjectServiceMaterial._meta.get_fields()}
        self.assertEqual(fields, {"id", "service_line", "item"})


class DefaultItemsPricingTests(DefaultItemsBase):
    def test_service_total_is_qty_times_price_without_items(self):
        line = self.save([(self.sheet, True), (self.channel, True)], qty="2.5", price="1000000")
        self.assertEqual(rows.service_line_total(line), Decimal("2500000"))
        self.assertEqual(rows.proforma_summary(self.project)["grand_total"], Decimal("2500000"))

    def test_only_ticked_items_are_saved(self):
        line = self.save([(self.sheet, True), (self.channel, False)])
        self.assertEqual(self.saved_items(line), {self.sheet.pk})

    def test_unticking_removes_item_and_reticking_restores_it(self):
        line = self.save([(self.sheet, True)])
        self.assertEqual(self.saved_items(line), {self.sheet.pk})
        line = self.save([(self.sheet, False)], pk=line.pk)
        self.assertEqual(self.saved_items(line), set())
        line = self.save([(self.sheet, True)], pk=line.pk)
        self.assertEqual(self.saved_items(line), {self.sheet.pk})

    def test_same_item_twice_is_saved_once(self):
        r = rows.parse_service_row(json.dumps([{
            "service_id": self.service.pk, "qty": "1", "unit_price": "1000000",
            "materials": [{"item_id": self.sheet.pk, "on": True}, {"item_id": self.sheet.pk, "on": True}]
        }]))
        line = rows.save_service_line(project=self.project, actor=self.acc, row=r)
        self.assertEqual(line.materials.count(), 1)

    def test_inactive_item_is_refused_unless_already_in_project(self):
        with self.assertRaises(ValueError) as cm:
            self.save([(self.dead, True)])
        self.assertIn("غیرفعال", str(cm.exception))

        line = self.save([(self.dead, False)])
        self.assertEqual(self.saved_items(line), set())

        ProjectServiceMaterial.objects.create(service_line=line, item=self.dead)
        line2 = self.save([(self.dead, True)], pk=line.pk)
        self.assertIn(self.dead.pk, self.saved_items(line2))

    def test_unknown_item_is_refused(self):
        r = rows.parse_service_row(json.dumps([{
            "service_id": self.service.pk, "qty": "1", "unit_price": "1000000",
            "materials": [{"item_id": 999999, "on": True}]
        }]))
        with self.assertRaises(ValueError):
            rows.save_service_line(project=self.project, actor=self.acc, row=r)

    def test_old_save_proforma_syncs_only_ticked_items(self):
        from projects.proforma import parse_service_rows, save_proforma
        r = parse_service_rows(json.dumps([{
            "service_id": self.service.pk, "qty": "1", "unit_price": "500000",
            "materials": [{"item_id": self.sheet.pk, "on": True}, {"item_id": self.channel.pk, "on": False}]
        }]))
        save_proforma(project=self.project, actor=self.acc, service_rows=r)
        line = self.project.services.get()
        self.assertEqual(self.saved_items(line), {self.sheet.pk})


class DefaultItemsInitialTests(DefaultItemsBase):
    def test_initial_lists_saved_and_unsaved_active_defaults(self):
        line = self.save([(self.sheet, True)])
        init = rows.service_row_initial(line)
        mats = init["materials"]
        item_ids = [m["item_id"] for m in mats]
        self.assertIn(self.sheet.pk, item_ids)
        self.assertIn(self.channel.pk, item_ids)
        self.assertNotIn(self.dead.pk, item_ids)
        sheet_mat = next(m for m in mats if m["item_id"] == self.sheet.pk)
        channel_mat = next(m for m in mats if m["item_id"] == self.channel.pk)
        self.assertTrue(sheet_mat["on"])
        self.assertFalse(channel_mat["on"])

    def test_initial_item_rows_have_no_price_or_qty(self):
        line = self.save([(self.sheet, True)])
        init = rows.service_row_initial(line)
        for m in init["materials"]:
            self.assertTrue(set(m.keys()).issubset({"pk", "item_id", "on"}))


class DefaultItemsPreviewTests(DefaultItemsBase):
    def test_preview_reports_added_and_removed_items(self):
        line = self.save([(self.sheet, True)])
        r = svc_row(self.service, [(self.channel, True)], pk=line.pk)
        prev = rows.preview_change(project=self.project, actor=self.acc, kind="service", row=r)
        self.assertFalse(prev["same"])
        labels = [c["label"] for c in prev["changes"]]
        self.assertIn("اضافه به فرم مصرف", labels)
        self.assertIn("حذف از فرم مصرف", labels)
        self.assertEqual(prev["grand_before"], prev["grand_after"])

    def test_preview_is_same_when_nothing_changed(self):
        line = self.save([(self.sheet, True)])
        r = svc_row(self.service, [(self.sheet, True)], pk=line.pk)
        prev = rows.preview_change(project=self.project, actor=self.acc, kind="service", row=r)
        self.assertTrue(prev["same"])


class DefaultItemsInvoiceTests(DefaultItemsBase):
    def test_invoice_lines_use_service_qty_and_unit_price(self):
        self.save([(self.sheet, True)], qty="3", price="2000000")
        lines = build_invoice_lines(self.project)
        self.assertEqual(len(lines), 1)
        l = lines[0]
        self.assertEqual(l.title, self.service.name)
        self.assertEqual(l.qty, Decimal("3"))
        self.assertEqual(l.unit_price, Decimal("2000000"))
        self.assertIsNone(l.cost_snapshot)

    def test_preview_lines_equal_real_invoice_lines(self):
        self.save([(self.sheet, True)], qty="2", price="1500000")
        preview = build_invoice_lines(self.project)
        inv = generate_invoice_for_project(self.project)
        real = list(inv.lines.order_by("pk"))
        self.assertEqual([(l.title, l.qty, l.unit_price, l.total) for l in preview],
                         [(l.title, l.qty, l.unit_price, l.total) for l in real])

    def test_half_rounding_matches_summary_and_invoice(self):
        self.save([], qty="0.50", price="1001")
        summary_total = rows.proforma_summary(self.project)["grand_total"]
        inv_line = build_invoice_lines(self.project)[0]
        self.assertEqual(summary_total, Decimal("501"))
        self.assertEqual(inv_line.total, Decimal("501"))


class DefaultItemsUsageTests(DefaultItemsBase):
    def setUp(self):
        super().setUp()
        wt = WorkflowTemplate.objects.create(name="چرخه تست پیش‌فرض", is_default=True)
        st_tmpl = WorkflowStepTemplate.objects.create(template=wt, title="مرحله برش", kind=StageKind.CUTTING, order=1)
        self.stage = ProjectStage.objects.create(project=self.project, step_template=st_tmpl, title="مرحله برش",
                                                  kind=StageKind.CUTTING, order=1,
                                                  status=ProjectStage.Status.IN_PROGRESS, assigned_to=self.tech)
        self.line = self.save([(self.sheet, True), (self.channel, True)])

    def test_usage_form_lists_ticked_items_including_manufactured(self):
        ctx = usage_context(self.tech, self.stage)
        item_ids = {r["item"].pk for r in ctx["rows"]}
        self.assertEqual(item_ids, {self.sheet.pk, self.channel.pk})
        self.assertNotIn(self.flange.pk, item_ids)

    def test_manufactured_usage_never_touches_stock(self):
        before_moves = StockMovement.objects.count()
        res = set_usage(stage=self.stage, item_id=self.channel.pk, qty_raw="3", actor=self.tech)
        self.assertEqual(res["short"], "")
        u = StageUsage.objects.get(stage=self.stage, item=self.channel)
        self.assertEqual(u.qty, Decimal("3"))
        self.assertEqual(u.deducted, Decimal("3"))
        self.assertEqual(StockMovement.objects.count(), before_moves)

    def test_manufactured_is_out_of_reconciliation_but_in_usage_by_stage(self):
        set_usage(stage=self.stage, item_id=self.sheet.pk, qty_raw="2", actor=self.tech)
        set_usage(stage=self.stage, item_id=self.channel.pk, qty_raw="3", actor=self.tech)
        recon_items = {r["item"].pk for r in accounting.project_reconciliation(self.project)}
        self.assertEqual(recon_items, {self.sheet.pk})

        from projects.usage import project_usage_by_stage
        usage_items = {r["item"].pk for g in project_usage_by_stage(self.project) for r in g["rows"]}
        self.assertIn(self.channel.pk, usage_items)
        self.assertIn(self.sheet.pk, usage_items)

    def test_reconciliation_rows_have_no_planned_key(self):
        set_usage(stage=self.stage, item_id=self.sheet.pk, qty_raw="2", actor=self.tech)
        recon = accounting.project_reconciliation(self.project)
        self.assertNotIn("planned", recon[0])


class DefaultItemsViewTests(DefaultItemsBase):
    def test_fragment_context_carries_defaults_and_manufactured_flag(self):
        client = Client()
        client.force_login(self.acc)
        resp = client.get(reverse("projects:proforma_body", args=[self.project.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        svc_data = next(s for s in resp.context["services_data"] if s["id"] == self.service.id)
        self.assertEqual(set(svc_data["items"]), {self.sheet.pk, self.channel.pk})

        items_data = {i["id"]: i for i in resp.context["items_data"]}
        self.assertTrue(items_data[self.channel.pk]["manufactured"])
        for i in items_data.values():
            self.assertNotIn("margin", i)
        self.assertNotIn("has_global_margin", resp.context)

    def test_page_shows_ticked_item_names_and_no_prices(self):
        self.save([(self.sheet, True)])
        client = Client()
        client.force_login(self.acc)
        resp = client.get(reverse("projects:proforma_editor", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertIn("کالاهای فرم مصرف", html)
        self.assertIn(self.sheet.name, html)
        self.assertNotIn("قانون سود", html)


class ServiceItemsLeftoversTests(SimpleTestCase):
    def test_margin_and_stale_leftovers_are_gone(self):
        base = settings.BASE_DIR
        body_html = (base / "templates/projects/partials/proforma_body.html").read_text(encoding="utf-8")
        self.assertNotIn("has_global_margin", body_html)
        self.assertNotIn("stale_items", body_html)

        views_py = (base / "projects/views.py").read_text(encoding="utf-8")
        self.assertNotIn("def _stale_items", views_py)

        proforma_py = (base / "projects/proforma.py").read_text(encoding="utf-8")
        self.assertNotIn("def material_totals", proforma_py)

    def test_proforma_js_has_no_item_price_logic(self):
        base = settings.BASE_DIR
        pf_js = (base / "static/js/proforma_page.js").read_text(encoding="utf-8")
        self.assertNotIn("matAuto", pf_js)
        self.assertNotIn("it.margin", pf_js)

        le_js = (base / "static/js/line_editor.js").read_text(encoding="utf-8")
        self.assertIn("level.remove", le_js)
