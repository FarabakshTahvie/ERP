import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, MarginRule
from inventory.models import Warehouse
from inventory.services import receive_stock
from projects.models import (
    Project, ProjectStage, StageKind, ProjectFile, ShipmentCheck, ExtraShipment,
    InstallLine, PartRequest, ProjectCost,
)
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake, advance_stage
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects.ops import ensure_install_lines, create_part_request, add_extra_shipment, add_project_cost, set_install_line


class OpsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = Party.objects.create(name="شریک ویو", is_partner=True, phone_number="09121112288")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.shipping_spec = Specialty.objects.get_or_create(name="راننده")[0]
        self.install_spec = Specialty.objects.get_or_create(name="نصاب")[0]
        self.keeper_spec = Specialty.objects.get_or_create(name="انباردار")[0]

        self.creator = User.objects.create_user(username="creator_view", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)

        self.driver = User.objects.create_user(username="driver_view", password="pw", role=User.Role.EMPLOYEE)
        self.driver.specialties.add(self.shipping_spec)

        self.installer = User.objects.create_user(username="installer_view", password="pw", role=User.Role.EMPLOYEE)
        self.installer.specialties.add(self.install_spec)

        self.keeper = User.objects.create_user(username="keeper_view", password="pw", role=User.Role.EMPLOYEE)
        self.keeper.specialties.add(self.keeper_spec)

        self.other_user = User.objects.create_user(username="other_view", password="pw", role=User.Role.EMPLOYEE)

        self.wh = Warehouse.objects.create(name="انبار مرکزی")
        self.item = Item.objects.create(name="لوله مسی", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("1000"))
        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=Decimal("1000"), received_at=timezone.now())

        MarginRule.objects.create(scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT, value=Decimal("20"), valid_from=timezone.now() - timezone.timedelta(days=1))

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )

        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید.")

        self.service = Service.objects.create(name="لوازم", unit=Item.Unit.METER)
        rows = parse_service_rows(json.dumps([{"service_id": self.service.id, "qty": "5", "unit_price": "10000", "materials": [{"item_id": self.item.id, "qty": "2"}]}]))
        save_proforma(project=self.project, actor=self.creator, service_rows=rows)
        self.invoice, _ = issue_proforma(project=self.project, actor=self.creator)

        self.gcode_stage = self.project.stages.get(kind=StageKind.GCODE)
        self.gcode_file = ProjectFile.objects.create(
            stage=self.gcode_stage, file=SimpleUploadedFile("f.nc", b"gcode"),
            kind=ProjectFile.Kind.GCODE, original_name="f.nc", uploaded_by=self.creator,
            is_attachment=True, cut_count=2,
        )

        self.ship_stage = self.project.stages.get(kind=StageKind.SHIPPING)
        self.ship_stage.assigned_to = self.driver
        self.ship_stage.status = ProjectStage.Status.IN_PROGRESS
        self.ship_stage.save()

        self.install_stage = self.project.stages.get(kind=StageKind.INSTALL)
        self.install_stage.assigned_to = self.installer
        self.install_stage.status = ProjectStage.Status.IN_PROGRESS
        self.install_stage.save()
        ensure_install_lines(self.install_stage)

    def test_ship_check_endpoint(self):
        url = reverse("projects:ship_check", args=[self.ship_stage.id])

        # GET method not allowed (405)
        self.client.force_login(self.driver)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

        # Invalid file ID (404)
        resp = self.client.post(url, {"file_id": "9999", "status": "sent"})
        self.assertEqual(resp.status_code, 404)

        # Missing reason on not_sent (400)
        resp = self.client.post(url, {"file_id": self.gcode_file.id, "status": "not_sent", "reason": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("error", resp.json())

        # Success (200)
        resp = self.client.post(url, {"file_id": self.gcode_file.id, "status": "sent", "reason": ""})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_install_line_endpoint(self):
        line = self.install_stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)
        url = reverse("projects:install_line", args=[self.install_stage.id])

        self.client.force_login(self.installer)

        # Line from different stage returns 404
        other_stage = self.project.stages.get(order=1)
        resp = self.client.post(reverse("projects:install_line", args=[other_stage.id]), {"line_id": line.id, "status": "ok"})
        self.assertEqual(resp.status_code, 404)

        # Success update
        resp = self.client.post(url, {"line_id": line.id, "status": "ok", "qty": "3"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["delta"], "1.0000")

    def test_final_review_access_and_completion(self):
        url = reverse("projects:final_review", args=[self.project.id])

        # Other tech gets 404
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(url).status_code, 404)

        # Creator gets 200
        self.client.force_login(self.creator)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "projects/final_review.html")

        # POST without comment fails
        resp = self.client.post(url, {"comment": ""})
        self.assertEqual(resp.status_code, 302) # Redirects back with error message
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.status, Project.Status.COMPLETED)

        # Final review stage
        rev_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        rev_stage.status = ProjectStage.Status.IN_PROGRESS
        rev_stage.assigned_to = self.creator
        rev_stage.save()

        # Approve final review
        resp = self.client.post(url, {"comment": "تایید نهایی پروژه"})
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETED)

    def test_financial_isolation_invoice_unaffected(self):
        invoice_total_before = self.invoice.total_amount
        lines_count_before = self.invoice.lines.count()

        # Add all phase 3 items
        add_extra_shipment(stage=self.ship_stage, item_id=self.item.id, qty_raw="3", note="کالای مازاد ارسال", actor=self.driver)
        mat_line = self.install_stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)
        set_install_line(line=mat_line, status="ok", actual_qty_raw="5", reason="", actor=self.installer) # delta +3
        req = create_part_request(stage=self.install_stage, item_id=self.item.id, qty_raw="2", note="نیاز به قطعه", actor=self.installer)
        add_project_cost(project=self.project, kind="part_shipping", title="ارسال قطعه", amount_raw="50000", actor=self.creator)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, invoice_total_before)
        self.assertEqual(self.invoice.lines.count(), lines_count_before)
