import json
from decimal import Decimal
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, ItemCategory, MarginRule
from projects.models import Project, ProjectStage, StageKind, ProjectService, ProjectServiceMaterial
from projects.workflow_v2 import build_workflow_v2
from projects.services import (
    create_project_from_technician_intake,
    advance_stage,
    project_prices_editable,
)
from projects.proforma import (
    parse_service_rows,
    save_proforma,
    issue_proforma,
    material_totals,
    service_line_total,
)


class ProformaPricingTests(TestCase):
    def setUp(self):
        self.internal = Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.acc_spec = Specialty.objects.create(name="حسابدار")
        self.creator = User.objects.create_user(username="creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)

        self.service = Service.objects.create(name="کانال‌کشی گالوانیزه", unit=Item.Unit.METER)
        self.item = Item.objects.create(
            name="ورق گالوانیزه 0.7",
            item_type=Item.ItemType.MATERIAL,
            unit=Item.Unit.SQUARE_METER,
            moving_average_cost=Decimal("200000"),
        )
        MarginRule.objects.create(
            scope=MarginRule.Scope.GLOBAL,
            value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("20"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.partner.id,
            visit_at=timezone.now(),
            issue_proforma=False,
        )
        first_stage = self.project.stages.first()
        advance_stage(first_stage, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید انجام شد.")

    def test_service_total_and_invoice_collapse(self):
        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "40", "unit_price": "850000",
            "materials": [{"item_id": self.item.id, "qty": "10"}],
        }]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        invoice, _ = issue_proforma(project=self.project, actor=self.accountant)
        # 40×850000 + 10×200000×1.2 = 34,000,000 + 2,400,000
        self.assertEqual(invoice.total_amount, Decimal("36400000"))
        line = invoice.lines.get()
        self.assertEqual((line.line_type, line.qty), ("service", 1))
        self.assertEqual(line.cost_snapshot, Decimal("2000000"))
        self.assertIn("40", line.title)
        self.assertFalse(invoice.lines.filter(line_type="material").exists())

    def test_material_totals_round_half_up(self):
        item = Item(moving_average_cost=Decimal("100"))
        cost, total = material_totals(item, Decimal("1"), Decimal("12.5"))
        self.assertEqual(total, Decimal("113"))  # 100 * 1.125 = 112.5 -> 113

    def test_service_without_materials_keeps_format(self):
        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "5", "unit_price": "500000",
            "materials": [],
        }]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        invoice, _ = issue_proforma(project=self.project, actor=self.accountant)
        line = invoice.lines.get()
        self.assertEqual((line.line_type, line.qty, line.unit_price), ("service", Decimal("5"), Decimal("500000")))

    def test_advance_stage_proforma_guard(self):
        proforma_st = self.project.stages.filter(kind=StageKind.PROFORMA).first()
        self.assertEqual(proforma_st.status, ProjectStage.Status.IN_PROGRESS)
        with self.assertRaises(ValueError):
            advance_stage(proforma_st, actor=self.accountant, new_status=ProjectStage.Status.DONE, comment="تکمیل دستی")

    def test_issue_proforma_without_services_fails(self):
        with self.assertRaises(ValueError):
            issue_proforma(project=self.project, actor=self.accountant)

    def test_stale_items_warning_and_cleared_on_save(self):
        # 1. Initially create proforma
        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "10", "unit_price": "100000",
            "materials": [{"item_id": self.item.id, "qty": "5"}],
        }]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)

        # 2. Check editor page - initially no stale items
        self.client.force_login(self.accountant)
        url = reverse("projects:proforma_editor", args=[self.project.id])
        resp = self.client.get(url)
        self.assertEqual(resp.context["stale_items"], [])

        # 3. Cost changed externally
        self.item.moving_average_cost = Decimal("300000")
        self.item.save()

        # Check editor page - stale items now contains the item name
        resp = self.client.get(url)
        self.assertIn(self.item.name, resp.context["stale_items"])

        # 4. Save proforma again - should update snapshot and clear stale warning
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        resp = self.client.get(url)
        self.assertEqual(resp.context["stale_items"], [])

    def test_pk_injection_prevented(self):
        p2, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )
        s1 = ProjectService.objects.create(project=p2, service=self.service, qty=1, unit_price=1000)
        m1 = ProjectServiceMaterial.objects.create(service_line=s1, item=self.item, qty=1, line_total=1000)

        # Trying to update self.project service with pk of m1 from p2
        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "1", "unit_price": "1000",
            "materials": [{"pk": m1.pk, "item_id": self.item.id, "qty": "5"}],
        }]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        # m1 on p2 must not be modified or moved
        m1.refresh_from_db()
        self.assertEqual(m1.service_line_id, s1.pk)
        self.assertEqual(m1.qty, Decimal("1"))


class ProformaViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.internal = Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.acc_spec = Specialty.objects.create(name="حسابدار")
        self.creator = User.objects.create_user(username="creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.other_tech = User.objects.create_user(username="other_tech", password="pw", role=User.Role.EMPLOYEE)
        self.admin = User.objects.create_user(username="admin_u", password="pw", role=User.Role.ADMIN, is_staff=True)

        self.service = Service.objects.create(name="سرویس ۱")
        self.item = Item.objects.create(name="کالا ۱", moving_average_cost=Decimal("1000"))

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )

    def test_proforma_editor_access(self):
        url = reverse("projects:proforma_editor", args=[self.project.id])
        # Other tech -> 404
        self.client.force_login(self.other_tech)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

        # Creator (no longer can edit pricing) -> 404
        self.client.force_login(self.creator)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

        # Accountant -> 200
        self.client.force_login(self.accountant)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Admin -> 200
        self.client.force_login(self.admin)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_validation_error_keeps_user_input(self):
        self.client.force_login(self.accountant)
        url = reverse("projects:proforma_editor", args=[self.project.id])
        invalid_json = json.dumps([{"service_id": 99999, "qty": "1", "unit_price": "100", "materials": []}])
        resp = self.client.post(url, {"services_json": invalid_json, "action": "save"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("initial_rows", resp.context)
        self.assertEqual(resp.context["initial_rows"][0]["service_id"], 99999)
