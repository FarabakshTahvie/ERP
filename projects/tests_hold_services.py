from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.models import Party, Specialty
from finance.models import Invoice
from projects.models import Project, ProjectStage, StageKind, WorkflowStepTemplate, WorkflowTemplate
from projects.services import (
    cancel_project_from_stage,
    held_project_ids,
    restore_cancelled_project,
    resume_suspended_stage,
    suspend_stage,
)


def SPEC(name):
    return Specialty.objects.get_or_create(name=name)[0]


class HoldServicesTests(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="hs_mgr", role=User.Role.ADMIN)
        self.accountant = mk(username="hs_acc", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(SPEC("حسابدار"))
        self.partner = Party.objects.create(name="شریک تست", is_partner=True, phone_number="09121112233")
        self.tpl = WorkflowTemplate.objects.create(name="قالب تست")
        self.step = WorkflowStepTemplate.objects.create(template=self.tpl, order=1, title="مرحله اول")
        self.project = Project.objects.create(
            name="پروژه تست", partner=self.partner, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS
        )
        self.stage = ProjectStage.objects.create(
            project=self.project, step_template=self.step, order=1, title="مرحله اول", status=ProjectStage.Status.IN_PROGRESS
        )

    def test_suspend_stage(self):
        # Success
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق به دلیل قطعی برق")
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.SUSPENDED)

        # No reason -> ValueError
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()
        with self.assertRaises(ValueError):
            suspend_stage(self.stage, actor=self.manager, comment="   ")

    def test_resume_suspended_stage(self):
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        # Non-manager -> ValueError
        with self.assertRaises(ValueError):
            resume_suspended_stage(self.stage, actor=self.accountant, comment="بازگشت")

        # Success by manager
        resume_suspended_stage(self.stage, actor=self.manager, comment="رفع مشکل")
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.IN_PROGRESS)

    def test_cancel_project_from_stage(self):
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        inv = Invoice.objects.create(
            project=self.project, number="INV-H-1", billed_party=self.partner, total_amount=Decimal("1000"), issue_date=timezone.localdate()
        )
        # Non-manager -> ValueError
        with self.assertRaises(ValueError):
            cancel_project_from_stage(self.stage, actor=self.accountant, comment="لغو", cancel_invoice=True)

        # Success by manager with invoice cancel
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو نهایی", cancel_invoice=True)
        self.project.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

    def test_restore_cancelled_project(self):
        inv = Invoice.objects.create(
            project=self.project, number="INV-RESTORE-1", billed_party=self.partner, total_amount=Decimal("1000"), issue_date=timezone.localdate()
        )
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو", cancel_invoice=True)
        self.project.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

        # Non-manager -> ValueError
        with self.assertRaises(ValueError):
            restore_cancelled_project(self.project, actor=self.accountant, comment="بازگشت")

        # Success by manager without restore_invoice
        restore_cancelled_project(self.project, actor=self.manager, comment="برگشت از لغو", restore_invoice=False)
        self.project.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.IN_PROGRESS)
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

        # Cancel again and restore with restore_invoice=True
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو دوباره", cancel_invoice=False)
        restore_cancelled_project(self.project, actor=self.manager, comment="برگشت از لغو با فاکتور", restore_invoice=True)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.SENT)

    def test_restore_cancelled_project_waiting_approval(self):
        # مرحله‌ی منتظر تایید بدون درخواست باز، درخواست تازه می‌گیرد
        self.stage.status = ProjectStage.Status.WAITING_APPROVAL
        self.stage.save()
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

        restore_cancelled_project(self.project, actor=self.manager, comment="برگشت")
        self.project.refresh_from_db()
        self.stage.refresh_from_db()
        from projects.models import StageApproval
        self.assertTrue(self.stage.approvals.filter(decision=StageApproval.Decision.PENDING).exists())

    def test_cancelled_project_guards(self):
        # گارد لغو: advance_stage، claim_stage، transfer_stage، add_stage_file و set_cut روی پروژه‌ی لغو‌شده خطا می‌دهند
        tech = User.objects.create_user(username="hs_tech", role=User.Role.EMPLOYEE)
        tech.specialties.add(SPEC("برش‌کار"))
        from projects.services import advance_stage, claim_stage, transfer_stage
        from projects.stage_ops import add_stage_file, set_cut
        from django.core.files.uploadedfile import SimpleUploadedFile

        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        self.project.refresh_from_db()

        with self.assertRaises(ValueError):
            advance_stage(self.stage, actor=self.manager, new_status=ProjectStage.Status.DONE, comment="تست")

        with self.assertRaises(ValueError):
            claim_stage(self.stage, user=self.manager)

        with self.assertRaises(ValueError):
            transfer_stage(self.stage, from_user=self.manager, to_user=tech, comment="انتقال")

        f = SimpleUploadedFile("test.txt", b"content")
        with self.assertRaises(ValueError):
            add_stage_file(stage=self.stage, uploaded=f, uploader=self.manager)

        gcode_step = WorkflowStepTemplate.objects.create(template=self.tpl, order=2, title="جی‌کد", kind=StageKind.GCODE)
        gcode_stage = ProjectStage.objects.create(project=self.project, step_template=gcode_step, order=2, title="جی‌کد", kind=StageKind.GCODE)
        from projects.models import ProjectFile
        pf = ProjectFile.objects.create(stage=gcode_stage, file="test.gcode", kind="gcode", cut_count=5)
        with self.assertRaises(ValueError):
            set_cut(file=pf, index=1, done=True, actor=self.manager)

    def test_cancel_does_not_reject_stage_and_logs_cancel_prefix(self):
        # لغو وضعیت مرحله را REJECTED نمی‌کند و رویداد با CANCEL_EVENT_PREFIX می‌گذارد
        from projects.services import CANCEL_EVENT_PREFIX
        from projects.models import StageEvent
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.save()
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو کامل")
        self.stage.refresh_from_db()
        self.assertNotEqual(self.stage.status, ProjectStage.Status.REJECTED)
        self.assertTrue(StageEvent.objects.filter(stage=self.stage, comment__startswith=CANCEL_EVENT_PREFIX).exists())

    def test_held_project_ids(self):
        self.assertNotIn(self.project.id, held_project_ids())
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        self.assertIn(self.project.id, held_project_ids())

        resume_suspended_stage(self.stage, actor=self.manager, comment="بازگشت")
        self.assertNotIn(self.project.id, held_project_ids())

        suspend_stage(self.stage, actor=self.manager, comment="تعلیق مجدد")
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        self.assertIn(self.project.id, held_project_ids())
