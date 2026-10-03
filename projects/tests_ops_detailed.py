import json
from decimal import Decimal
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
    InstallLine, PartRequest, ProjectCost, StageEvent,
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


class ShippingCheckTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک ۳", is_partner=True, phone_number="09121112255")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.acc_spec = Specialty.objects.get_or_create(name="حسابدار")[0]
        self.shipping_spec = Specialty.objects.get_or_create(name="راننده")[0]
        self.creator = User.objects.create_user(username="creator_sh", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="acc_sh", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.driver = User.objects.create_user(username="driver_sh", password="pw", role=User.Role.EMPLOYEE)
        self.driver.specialties.add(self.shipping_spec)
        self.wh = Warehouse.objects.create(name="انبار ۳")

        self.service = Service.objects.create(name="تست ارسال")
        self.item = Item.objects.create(name="کالای ارسال", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("1000"))
        MarginRule.objects.create(scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT, value=Decimal("20"), valid_from=timezone.now() - timezone.timedelta(days=1))

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False)

        # VISIT -> Done
        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید شد.")

        # PROFORMA
        rows = parse_service_rows(json.dumps([{"service_id": self.service.id, "qty": "10", "unit_price": "5000", "materials": []}]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        issue_proforma(project=self.project, actor=self.accountant)

        self.gcode_stage = self.project.stages.get(kind=StageKind.GCODE)
        self.gcode_file = ProjectFile.objects.create(
            stage=self.gcode_stage, file=SimpleUploadedFile("f.nc", b"gcode"),
            kind=ProjectFile.Kind.GCODE, original_name="f.nc", uploaded_by=self.creator,
            is_attachment=True, cut_count=5
        )

        self.stage = self.project.stages.get(kind=StageKind.SHIPPING)
        self.stage.assigned_to = self.driver
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()

    def test_not_sent_needs_reason(self):
        with self.assertRaises(ValueError) as cm:
            set_shipment_check(stage=self.stage, file=self.gcode_file, status="not_sent", reason=" ", actor=self.driver)
        self.assertIn("دلیل ارسال‌نشدن", str(cm.exception))

    def test_sent_clears_previous_reason(self):
        set_shipment_check(stage=self.stage, file=self.gcode_file, status="not_sent", reason="شکسته", actor=self.driver)
        chk = self.stage.shipment_checks.get()
        self.assertEqual(chk.status, "not_sent")
        self.assertEqual(chk.reason, "شکسته")

        set_shipment_check(stage=self.stage, file=self.gcode_file, status="sent", reason="دلخواه", actor=self.driver)
        chk.refresh_from_db()
        self.assertEqual(chk.status, "sent")
        self.assertEqual(chk.reason, "")

    def test_idempotent_creation(self):
        set_shipment_check(stage=self.stage, file=self.gcode_file, status="sent", reason="", actor=self.driver)
        set_shipment_check(stage=self.stage, file=self.gcode_file, status="sent", reason="", actor=self.driver)
        self.assertEqual(self.stage.shipment_checks.count(), 1)

    def test_invalid_file_rejected(self):
        other_file = ProjectFile.objects.create(
            stage=self.gcode_stage, file=SimpleUploadedFile("f.dwg", b"dwg"),
            kind=ProjectFile.Kind.DWG, original_name="f.dwg", uploaded_by=self.creator,
            is_attachment=True, cut_count=None
        )
        with self.assertRaises(ValueError):
            set_shipment_check(stage=self.stage, file=other_file, status="sent", reason="", actor=self.driver)

    def test_completion_problem_with_missing_checks(self):
        # First upload image to satisfy upload requirement
        ProjectFile.objects.create(
            stage=self.stage, file=SimpleUploadedFile("img.jpg", b"img"),
            kind=ProjectFile.Kind.IMAGE, original_name="img.jpg", is_attachment=True
        )

        problem = stage_completion_problem(self.stage)
        self.assertIn("فایل هنوز «ارسال شد» یا «ارسال نشد» ثبت نشده", problem)

        set_shipment_check(stage=self.stage, file=self.gcode_file, status="sent", reason="", actor=self.driver)
        self.assertIsNone(stage_completion_problem(self.stage))

    def test_extra_shipment_ops(self):
        ex = add_extra_shipment(stage=self.stage, item_id=self.item.id, qty_raw="2.5", note="مازاد", actor=self.driver)
        self.assertEqual(ex.qty, Decimal("2.5"))
        self.assertEqual(ex.sale_total, Decimal("3000")) # 2.5 * 1000 * 1.2
        self.assertEqual(self.item.current_stock, 0) # No stock movement

        with self.assertRaises(ValueError):
            add_extra_shipment(stage=self.stage, item_id=self.item.id, qty_raw="0", note="x", actor=self.driver)

        # Delete extra shipment logs to StageEvent
        delete_extra_shipment(extra=ex, actor=self.driver)
        self.assertEqual(ExtraShipment.objects.count(), 0)
        self.assertTrue(StageEvent.objects.filter(stage=self.stage, comment__icontains="حذف شد").exists())


class InstallLinesTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک ۴", is_partner=True, phone_number="09121112266")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.acc_spec = Specialty.objects.get_or_create(name="حسابدار")[0]
        self.install_spec = Specialty.objects.get_or_create(name="نصاب")[0]
        self.creator = User.objects.create_user(username="creator_ins", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="acc_ins", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.installer = User.objects.create_user(username="installer_ins", password="pw", role=User.Role.EMPLOYEE)
        self.installer.specialties.add(self.install_spec)
        self.wh = Warehouse.objects.create(name="انبار ۴")

        self.service = Service.objects.create(name="خدمت تست", unit=Item.Unit.METER)
        self.item = Item.objects.create(name="کالای تست", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("500"))
        MarginRule.objects.create(scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT, value=Decimal("20"), valid_from=timezone.now() - timezone.timedelta(days=1))

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False)

        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید.")

        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "5", "unit_price": "2000",
            "materials": [{"item_id": self.item.id, "qty": "10"}],
        }]))
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        issue_proforma(project=self.project, actor=self.accountant)

        self.stage = self.project.stages.get(kind=StageKind.INSTALL)
        self.stage.assigned_to = self.installer
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()

    def test_ensure_install_lines_idempotent(self):
        ensure_install_lines(self.stage)
        count_before = self.stage.install_lines.count()
        self.assertEqual(count_before, 2) # 1 service + 1 material

        ensure_install_lines(self.stage)
        self.assertEqual(self.stage.install_lines.count(), count_before)

    def test_set_install_line_validation_and_calculations(self):
        ensure_install_lines(self.stage)
        srv_line = self.stage.install_lines.get(kind=InstallLine.Kind.SERVICE)
        mat_line = self.stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)

        # OK with empty qty defaults to planned
        set_install_line(line=mat_line, status="ok", actual_qty_raw="", reason="", actor=self.installer)
        mat_line.refresh_from_db()
        self.assertEqual(mat_line.actual_qty, Decimal("10"))
        self.assertEqual(mat_line.delta_qty, Decimal("0"))
        self.assertEqual(mat_line.delta_sale, Decimal("0"))

        # OK with custom qty
        set_install_line(line=mat_line, status="ok", actual_qty_raw="8", reason="", actor=self.installer)
        mat_line.refresh_from_db()
        self.assertEqual(mat_line.actual_qty, Decimal("8"))
        self.assertEqual(mat_line.delta_qty, Decimal("-2"))
        self.assertEqual(mat_line.delta_sale, Decimal("-1200")) # -2 * 500 * 1.2

        # Invalid qty
        with self.assertRaises(ValueError):
            set_install_line(line=mat_line, status="ok", actual_qty_raw="-1", reason="", actor=self.installer)


class ProjectCostAndReviewTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک ۵", is_partner=True, phone_number="09121112277")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.creator = User.objects.create_user(username="creator_rev", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.acc_spec = Specialty.objects.get_or_create(name="حسابدار")[0]
        self.accountant = User.objects.create_user(username="acc_rev", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.other_user = User.objects.create_user(username="other_rev", password="pw", role=User.Role.EMPLOYEE)

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False)

    def test_complete_stage_final_review_requires_via_review(self):
        rev_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        rev_stage.status = ProjectStage.Status.IN_PROGRESS
        rev_stage.assigned_to = self.creator
        rev_stage.save()
        with self.assertRaises(ValueError) as cm:
            complete_stage(stage=rev_stage, actor=self.creator, comment="تکمیل بدون بازبینی", via_review=False)
        self.assertIn("بازبینی نهایی فقط از صفحه‌ی «بازبینی نهایی» تایید می‌شود", str(cm.exception))

    def test_cost_addition_and_deletion(self):
        with self.assertRaises(ValueError):
            add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="-1000", actor=self.accountant)

        # creator cannot add cost
        with self.assertRaises(ValueError):
            add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="15000", actor=self.creator)

        cost = add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="15000", actor=self.accountant)
        self.assertEqual(self.project.recorded_costs.count(), 1)
        self.assertEqual(cost.amount, Decimal("15000"))

        with self.assertRaises(ValueError):
            delete_project_cost(cost=cost, actor=self.other_user)

        with self.assertRaises(ValueError):
            delete_project_cost(cost=cost, actor=self.creator)

        delete_project_cost(cost=cost, actor=self.accountant)
        self.assertEqual(self.project.recorded_costs.count(), 0)
