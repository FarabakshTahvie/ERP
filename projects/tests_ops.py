import json
from decimal import Decimal
from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, MarginRule
from inventory.models import Warehouse, StockMovement
from inventory.services import receive_stock
from projects.models import (
    Project, ProjectStage, StageKind, ProjectFile, ShipmentCheck, ExtraShipment,
    InstallLine, PartRequest, ProjectCost,
)
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake, advance_stage
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects.stage_ops import add_stage_file, complete_stage, stage_completion_problem
from projects.ops import (
    set_shipment_check, add_extra_shipment, delete_extra_shipment,
    ensure_install_lines, set_install_line, create_part_request,
    issue_part_request, reject_part_request, cancel_part_request,
    add_project_cost, delete_project_cost, final_review_data,
)


class InstallShortageExcessTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.install_spec = Specialty.objects.get_or_create(name="نصاب")[0]
        self.creator = User.objects.create_user(username="creator_ph3", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.installer = User.objects.create_user(username="installer_ph3", password="pw", role=User.Role.EMPLOYEE)
        self.installer.specialties.add(self.install_spec)
        self.wh = Warehouse.objects.create(name="انبار مرکزی")

        self.service = Service.objects.create(name="کانال‌کشی گالوانیزه", unit=Item.Unit.METER)
        self.item = Item.objects.create(
            name="ورق گالوانیزه 0.7",
            item_type=Item.ItemType.MATERIAL,
            unit=Item.Unit.SQUARE_METER,
            moving_average_cost=Decimal("200000"),
        )
        receive_stock(item=self.item, warehouse=self.wh, qty=100, unit_cost=Decimal("200000"), received_at=timezone.now())

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

        # Complete intake
        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید شد.")

        # Proforma
        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "40", "unit_price": "850000",
            "materials": [{"item_id": self.item.id, "qty": "10"}],
        }]))
        save_proforma(project=self.project, actor=self.creator, service_rows=rows)
        issue_proforma(project=self.project, actor=self.creator)

        self.stage = self.project.stages.get(kind=StageKind.INSTALL)
        self.stage.assigned_to = self.installer
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()
        add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("install.jpg", b"x"), uploader=self.installer)
        ensure_install_lines(self.stage)

    def _mat(self):
        return self.stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)

    def test_excess_is_priced_with_proforma_snapshot_not_live_cost(self):
        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=900000, received_at=timezone.now())  # میانگین زنده عوض شد
        set_install_line(line=self._mat(), status="ok", actual_qty_raw="12", reason="", actor=self.installer)
        line = self._mat()
        self.assertEqual(line.delta_qty, Decimal("2"))
        self.assertEqual(line.delta_sale, Decimal("480000"))   # 2 × 200000 × 1.2
        self.assertFalse(self.project.invoice.lines.filter(title__icontains=self.item.name).exists())   # روی فاکتور نمی‌آید

    def test_not_ok_needs_reason_and_creator_edits_after_stage_done_but_installer_cannot(self):
        with self.assertRaises(ValueError):
            set_install_line(line=self._mat(), status="not_ok", actual_qty_raw="", reason="  ", actor=self.installer)
        for line in self.stage.install_lines.all():
            set_install_line(line=line, status="ok", actual_qty_raw="", reason="", actor=self.installer)
        complete_stage(stage=self.stage, actor=self.installer, comment="تمام")
        set_install_line(line=self._mat(), status="ok", actual_qty_raw="9", reason="", actor=self.creator)   # ثبت‌کننده همیشه
        self.assertEqual(self._mat().delta_qty, Decimal("-1"))
        with self.assertRaises(ValueError):
            set_install_line(line=self._mat(), status="ok", actual_qty_raw="9", reason="", actor=self.installer)


class PartRequestIssueTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک آزمایشی ۲", is_partner=True, phone_number="09121112244")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.install_spec = Specialty.objects.get_or_create(name="نصاب")[0]
        self.keeper_spec = Specialty.objects.get_or_create(name="انباردار")[0]
        self.creator = User.objects.create_user(username="creator_pr", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.installer = User.objects.create_user(username="installer_pr", password="pw", role=User.Role.EMPLOYEE)
        self.installer.specialties.add(self.install_spec)
        self.keeper = User.objects.create_user(username="keeper_pr", password="pw", role=User.Role.EMPLOYEE)
        self.keeper.specialties.add(self.keeper_spec)
        self.wh = Warehouse.objects.create(name="انبار مرکزی ۲")

        self.service = Service.objects.create(name="کانال‌کشی", unit=Item.Unit.METER)
        self.item = Item.objects.create(
            name="ورق استیل",
            item_type=Item.ItemType.MATERIAL,
            unit=Item.Unit.SQUARE_METER,
            moving_average_cost=Decimal("150000"),
        )
        receive_stock(item=self.item, warehouse=self.wh, qty=3, unit_cost=Decimal("100000"), received_at=timezone.now() - timezone.timedelta(days=2))
        receive_stock(item=self.item, warehouse=self.wh, qty=5, unit_cost=Decimal("200000"), received_at=timezone.now())

        MarginRule.objects.create(
            scope=MarginRule.Scope.GLOBAL,
            value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("20"),
            valid_from=timezone.now() - timezone.timedelta(days=1),
        )

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )

        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید.")

        rows = parse_service_rows(json.dumps([{"service_id": self.service.id, "qty": "10", "unit_price": "500000", "materials": []}]))
        save_proforma(project=self.project, actor=self.creator, service_rows=rows)
        issue_proforma(project=self.project, actor=self.creator)

        self.stage = self.project.stages.get(kind=StageKind.INSTALL)
        self.stage.assigned_to = self.installer
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()
        add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("ins.jpg", b"x"), uploader=self.installer)

    def test_issue_consumes_fifo_records_cost_and_blocks_second_issue(self):
        req = create_part_request(stage=self.stage, item_id=self.item.id, qty_raw="4", note="کم آمد", actor=self.installer)
        issue_part_request(req=req, actor=self.keeper)
        req.refresh_from_db()
        self.assertEqual(req.status, "issued")
        self.assertEqual(req.cost_total, Decimal("500000"))      # 3×100000 + 1×200000
        self.assertEqual(req.sale_total, Decimal("600000"))      # ×1.2
        self.assertEqual(self.item.current_stock, Decimal("4"))
        self.assertTrue(StockMovement.objects.filter(related_object_id=self.project.id, qty=3).exists())
        with self.assertRaises(ValueError):
            issue_part_request(req=req, actor=self.keeper)
        self.assertEqual(self.item.current_stock, Decimal("4"))   # دوباره کم نشده

    def test_only_keeper_decides_reject_needs_reason_and_pending_blocks_install_completion(self):
        ensure_install_lines(self.stage)
        for line in self.stage.install_lines.all():
            set_install_line(line=line, status="ok", actual_qty_raw="", reason="", actor=self.installer)
        req = create_part_request(stage=self.stage, item_id=self.item.id, qty_raw="1", note="x", actor=self.installer)
        with self.assertRaises(ValueError):
            issue_part_request(req=req, actor=self.installer)
        with self.assertRaises(ValueError):
            reject_part_request(req=req, actor=self.keeper, reason=" ")
        self.assertIn("درخواست قطعه", stage_completion_problem(self.stage))
        reject_part_request(req=req, actor=self.keeper, reason="موجود نیست")
        self.assertNotIn("درخواست قطعه", stage_completion_problem(self.stage) or "")
