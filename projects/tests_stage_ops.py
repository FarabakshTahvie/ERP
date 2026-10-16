import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from utils.test_helpers import make_image_file
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, ItemCategory, MarginRule
from inventory.models import Warehouse
from inventory.services import receive_stock
from projects.models import Project, ProjectStage, StageKind, ProjectFile, ProjectService, ProjectServiceMaterial
from projects.workflow_v3 import build_workflow_v3
from projects.services import create_project_from_technician_intake, advance_stage, client_preview_files
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects.stage_ops import (
    add_stage_file, stage_completion_problem, complete_stage,
    parse_cut_count, upload_requirement
)


class DesignPreviewDecisionTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.acc_spec = Specialty.objects.create(name="حسابدار")
        self.creator = User.objects.create_user(username="creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="acc_stage_ops", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)

        self.design_spec = Specialty.objects.get_or_create(name="طراح اتوکد")[0]
        self.designer = User.objects.create_user(username="designer", password="pw", role=User.Role.EMPLOYEE)
        self.designer.specialties.add(self.design_spec)

        build_workflow_v3(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )

        # Complete stages 1, 2, 3 to reach stage 4 (DESIGN_INITIAL)
        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید شد.")

        st2 = self.project.stages.get(order=2)
        Service.objects.create(name="خدمت تست")
        srv = Service.objects.first()
        rows = parse_service_rows(json.dumps([{"service_id": srv.id, "qty": "1", "unit_price": "1000", "materials": []}]))
        save_proforma(
            project=self.project, actor=self.accountant,
            service_rows=rows
        )
        issue_proforma(project=self.project, actor=self.accountant)

        st3 = self.project.stages.get(order=3)
        st3.assigned_to = self.creator
        st3.save()
        advance_stage(st3, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="تایید شد.")

        self.design_stage = self.project.stages.get(kind=StageKind.DESIGN_INITIAL)
        self.design_stage.assigned_to = self.designer
        self.design_stage.status = ProjectStage.Status.IN_PROGRESS
        self.design_stage.save()

    def _stage(self):
        stage = self.project.stages.get(kind=StageKind.DESIGN_INITIAL)
        add_stage_file(stage=stage, uploaded=SimpleUploadedFile("نقشه ۱.dwg", b"x"), uploader=self.designer)
        add_stage_file(stage=stage, uploaded=SimpleUploadedFile("پیش‌نمایش.pdf", b"x"), uploader=self.designer)
        return stage

    def test_unticked_completes_and_shows_nothing(self):
        stage = self._stage()
        complete_stage(stage=stage, actor=self.designer, comment="تمام")
        stage.refresh_from_db()
        self.assertEqual(stage.status, ProjectStage.Status.DONE)
        self.assertFalse(stage.client_preview)
        self.assertEqual(client_preview_files(stage), [])
        self.assertEqual(self.project.stages.get(order=5).status, ProjectStage.Status.IN_PROGRESS)

    def test_ticked_needs_a_previewable_file(self):
        stage = self.project.stages.get(kind=StageKind.DESIGN_INITIAL)
        add_stage_file(stage=stage, uploaded=SimpleUploadedFile("فقط.dwg", b"x"), uploader=self.designer)
        self.assertIsNone(stage_completion_problem(stage))
        with self.assertRaises(ValueError) as cm:
            complete_stage(stage=stage, actor=self.designer, comment="تمام", show_to_client=True)
        self.assertIn("عکس یا PDF", str(cm.exception))
        stage.refresh_from_db()
        self.assertEqual(stage.status, ProjectStage.Status.IN_PROGRESS)

    def test_ticked_marks_stage_and_exposes_every_file_except_gcode(self):
        stage = self._stage()
        add_stage_file(stage=stage, uploaded=SimpleUploadedFile("cut.nc", b"x"), uploader=self.designer)
        complete_stage(stage=stage, actor=self.designer, comment="تمام", show_to_client=True)
        stage.refresh_from_db()
        self.assertTrue(stage.client_preview)
        self.assertEqual({f.original_name for f in client_preview_files(stage)}, {"نقشه ۱.dwg", "پیش‌نمایش.pdf"})

    def test_no_customer_approval_is_created_and_project_flows_on(self):
        stage = self._stage()
        complete_stage(stage=stage, actor=self.designer, comment="تمام", show_to_client=True)
        self.assertFalse(self.project.stages.filter(status=ProjectStage.Status.WAITING_APPROVAL).exists())
        self.assertEqual(self.project.stages.get(order=5).status, ProjectStage.Status.IN_PROGRESS)

    def test_view_checkbox_sets_preview(self):
        stage = self._stage()
        c = Client()
        c.force_login(self.designer)
        c.post(reverse("projects:my_task_complete", args=[stage.id]), {"comment": "تمام", "show_to_client": "1"})
        stage.refresh_from_db()
        self.assertTrue(stage.client_preview)


class StageOpsDetailedTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.creator = User.objects.create_user(username="creator_ops", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)

        self.other_tech = User.objects.create_user(username="other_ops", password="pw", role=User.Role.EMPLOYEE)
        self.admin = User.objects.create_user(username="admin_ops", password="pw", role=User.Role.ADMIN, is_staff=True)

        build_workflow_v3(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )
        self.stage = self.project.stages.get(order=1)



    def test_fake_path_traversal_sanitized(self):
        self.stage.assigned_to = self.creator
        self.stage.save()
        f = add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("../../secret.txt", b"abc"), uploader=self.creator)
        self.assertEqual(f.original_name, "secret.txt")



    def test_file_size_exceeded_rejected(self):
        self.stage.assigned_to = self.creator
        self.stage.save()
        big = SimpleUploadedFile("big.zip", b"x", content_type="application/zip")
        big.size = 25 * 1024 * 1024 + 1
        with self.assertRaises(ValueError) as cm:
            add_stage_file(stage=self.stage, uploaded=big, uploader=self.creator)
        self.assertIn("بیشتر از ۲۵ مگابایت", str(cm.exception))

    def test_upload_to_non_in_progress_stage_rejected(self):
        self.stage.assigned_to = self.creator
        self.stage.status = ProjectStage.Status.PENDING
        self.stage.save()
        with self.assertRaises(ValueError) as cm:
            add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("a.png", b"x"), uploader=self.creator)
        self.assertIn("در حال انجام", str(cm.exception))

    def test_unauthorized_technician_rejected(self):
        with self.assertRaises(ValueError):
            add_stage_file(stage=self.stage, uploaded=make_image_file("a.png"), uploader=self.other_tech)
        # Admin is allowed
        f = add_stage_file(stage=self.stage, uploaded=make_image_file("a.png"), uploader=self.admin)
        self.assertIsNotNone(f)



    def test_stage_completion_rules(self):
        # Visit stage
        self.stage.assigned_to = self.creator
        self.stage.save()
        self.assertIsNone(stage_completion_problem(self.stage))

        # Shipping stage requires image
        ship_st = self.project.stages.get(kind=StageKind.SHIPPING)
        self.assertEqual(upload_requirement(ship_st), "image")
        self.assertIn("عکس", stage_completion_problem(ship_st))
        ProjectFile.objects.create(
            stage=ship_st, file=SimpleUploadedFile("doc.pdf", b"x"),
            kind=ProjectFile.Kind.PDF, original_name="doc.pdf", is_attachment=True
        )
        self.assertIn("عکس", stage_completion_problem(ship_st))
        ProjectFile.objects.create(
            stage=ship_st, file=SimpleUploadedFile("photo.jpg", b"x"),
            kind=ProjectFile.Kind.IMAGE, original_name="photo.jpg", is_attachment=True
        )
        self.assertIsNone(stage_completion_problem(ship_st))


class SnapshotImmutabilityTests(TestCase):
    def setUp(self):
        self.internal = Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.acc_spec, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.creator = User.objects.create_user(username="creator2", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.accountant = User.objects.create_user(username="acc_stage_ops2", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.wh = Warehouse.objects.create(name="انبار مرکزی")

        self.service = Service.objects.create(name="کانال‌کشی")
        self.item = Item.objects.create(name="ورق گالوانیزه", moving_average_cost=Decimal("200000"))
        MarginRule.objects.create(scope="global", value_type="percent", value=Decimal("20"), valid_from=timezone.now() - timezone.timedelta(days=1))

        build_workflow_v3(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )
        st1 = self.project.stages.first()
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید.")

        rows = parse_service_rows(json.dumps([{
            "service_id": self.service.id, "qty": "40", "unit_price": "850000",
            "materials": [{"item_id": self.item.id, "qty": "10"}],
        }]))
        save_proforma(
            project=self.project, actor=self.accountant,
            service_rows=rows
        )
        self.invoice, _ = issue_proforma(project=self.project, actor=self.accountant)

    def test_changes_after_issue_do_not_touch_invoice_or_snapshots(self):
        before = list(self.invoice.lines.values_list("title", "qty", "unit_price", "total", "cost_snapshot"))
        total = self.invoice.total_amount
        mat = ProjectServiceMaterial.objects.get()
        snap = (mat.cost_snapshot, mat.margin_percent, mat.line_total)

        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=Decimal("900000"), received_at=timezone.now())
        MarginRule.objects.create(scope="global", value_type="percent", value=Decimal("50"), valid_from=timezone.now())
        self.item.name, self.service.name = "نام جدید کالا", "نام جدید خدمت"
        self.item.save()
        self.service.save()

        self.invoice.refresh_from_db()
        mat.refresh_from_db()
        self.assertEqual(list(self.invoice.lines.values_list("title", "qty", "unit_price", "total", "cost_snapshot")), before)
        self.assertEqual(self.invoice.total_amount, total)
        self.assertEqual((mat.cost_snapshot, mat.margin_percent, mat.line_total), snap)
