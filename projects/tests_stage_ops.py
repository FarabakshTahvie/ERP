import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, ItemCategory, MarginRule
from inventory.models import Warehouse
from inventory.services import receive_stock
from projects.models import Project, ProjectStage, StageKind, ProjectFile, ProjectService, ProjectServiceMaterial
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake, advance_stage
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects.stage_ops import (
    add_stage_file, stage_completion_problem, complete_stage,
    cuts_summary, set_cut, parse_cut_count, upload_requirement
)


class DesignApprovalDecisionTests(TestCase):
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

        build_workflow_v2(make_default=True)
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

    def test_no_approval_skips_approval_stage_and_hides_it(self):
        complete_stage(stage=self._stage(), actor=self.designer, comment="تمام", needs_approval=False)
        approval = self.project.stages.get(kind=StageKind.DESIGN_APPROVAL)
        self.assertEqual(approval.status, ProjectStage.Status.DONE)
        self.assertFalse(approval.client_visible)
        self.assertFalse(approval.approvals.exists())
        self.assertEqual(self.project.stages.get(order=6).status, ProjectStage.Status.IN_PROGRESS)

    def test_needs_approval_none_is_rejected_and_yes_goes_to_customer(self):
        stage = self._stage()
        with self.assertRaises(ValueError):
            complete_stage(stage=stage, actor=self.designer, comment="تمام", needs_approval=None)
        complete_stage(stage=stage, actor=self.designer, comment="تمام", needs_approval=True)
        approval = self.project.stages.get(kind=StageKind.DESIGN_APPROVAL)
        self.assertEqual(approval.status, ProjectStage.Status.WAITING_APPROVAL)
        self.assertTrue(approval.approvals.filter(decision="pending").exists())


    def test_rejection_path_and_second_rejection_decision(self):
        stage = self._stage()
        complete_stage(stage=stage, actor=self.designer, comment="ارسال برای مشتری", needs_approval=True)
        approval = self.project.stages.get(kind=StageKind.DESIGN_APPROVAL)

        # Reject approval stage
        advance_stage(approval, actor=self.creator, new_status=ProjectStage.Status.REJECTED, comment="رد شد.")
        stage.refresh_from_db()
        self.assertEqual(stage.status, ProjectStage.Status.IN_PROGRESS)

        # Complete design again with needs_approval=False
        complete_stage(stage=stage, actor=self.designer, comment="اصلاح شد بدون تایید", needs_approval=False)
        approval.refresh_from_db()
        self.assertEqual(approval.status, ProjectStage.Status.DONE)
        self.assertFalse(approval.client_visible)


class StageOpsDetailedTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.creator = User.objects.create_user(username="creator_ops", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)

        self.other_tech = User.objects.create_user(username="other_ops", password="pw", role=User.Role.EMPLOYEE)
        self.admin = User.objects.create_user(username="admin_ops", password="pw", role=User.Role.ADMIN, is_staff=True)

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )
        self.stage = self.project.stages.get(order=1)

    def test_file_original_name_and_duplicates_preserved(self):
        self.stage.assigned_to = self.creator
        self.stage.save()
        f1 = add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("نقشه آزمایشی ۱۲۳.dwg", b"111"), uploader=self.creator)
        f2 = add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("نقشه آزمایشی ۱۲۳.dwg", b"222"), uploader=self.creator)
        self.assertEqual(f1.original_name, "نقشه آزمایشی ۱۲۳.dwg")
        self.assertEqual(f2.original_name, "نقشه آزمایشی ۱۲۳.dwg")
        self.assertEqual(f1.display_name, f2.display_name)
        self.assertTrue(f1.is_current)
        self.assertTrue(f2.is_current)

    def test_fake_path_traversal_sanitized(self):
        self.stage.assigned_to = self.creator
        self.stage.save()
        f = add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("../../secret.txt", b"abc"), uploader=self.creator)
        self.assertEqual(f.original_name, "secret.txt")

    def test_stage_files_max_limit_enforced(self):
        self.stage.assigned_to = self.creator
        self.stage.save()
        for i in range(200):
            ProjectFile.objects.create(
                stage=self.stage, file=SimpleUploadedFile(f"f{i}.png", b"x"),
                kind=ProjectFile.Kind.IMAGE, original_name=f"f{i}.png",
                uploaded_by=self.creator, is_attachment=True
            )
        with self.assertRaises(ValueError) as cm:
            add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("overflow.png", b"x"), uploader=self.creator)
        self.assertIn("حداکثر 200 فایل", str(cm.exception))

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
            add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("a.png", b"x"), uploader=self.other_tech)
        # Admin is allowed
        f = add_stage_file(stage=self.stage, uploaded=SimpleUploadedFile("a.png", b"x"), uploader=self.admin)
        self.assertIsNotNone(f)

    def test_gcode_cut_count_parsing(self):
        self.assertEqual(parse_cut_count("۱۲"), 12)
        self.assertEqual(parse_cut_count(5), 5)
        with self.assertRaises(ValueError):
            parse_cut_count("0")
        with self.assertRaises(ValueError):
            parse_cut_count("1000")
        with self.assertRaises(ValueError):
            parse_cut_count("abc")

    def test_cutting_summary_and_set_cut_idempotent(self):
        gcode_st = self.project.stages.get(kind=StageKind.GCODE)
        cutting_st = self.project.stages.get(kind=StageKind.CUTTING)
        cutting_st.status = ProjectStage.Status.IN_PROGRESS
        cutting_st.assigned_to = self.creator
        cutting_st.save()

        f1 = ProjectFile.objects.create(
            stage=gcode_st, file=SimpleUploadedFile("f1.nc", b"x"),
            kind=ProjectFile.Kind.GCODE, original_name="f1.nc",
            uploaded_by=self.creator, is_attachment=True, cut_count=3
        )
        f2 = ProjectFile.objects.create(
            stage=gcode_st, file=SimpleUploadedFile("f2.nc", b"x"),
            kind=ProjectFile.Kind.GCODE, original_name="f2.nc",
            uploaded_by=self.creator, is_attachment=True, cut_count=2
        )

        tot, done = cuts_summary(self.project)
        self.assertEqual((tot, done), (5, 0))

        set_cut(file=f1, index=1, done=True, actor=self.creator)
        set_cut(file=f1, index=1, done=True, actor=self.creator)  # idempotent
        tot, done = cuts_summary(self.project)
        self.assertEqual((tot, done), (5, 1))

        set_cut(file=f1, index=1, done=False, actor=self.creator)
        tot, done = cuts_summary(self.project)
        self.assertEqual((tot, done), (5, 0))

        with self.assertRaises(ValueError):
            set_cut(file=f1, index=4, done=True, actor=self.creator)

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

        build_workflow_v2(make_default=True)
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
