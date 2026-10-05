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
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو", cancel_invoice=False)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)

        # Non-manager -> ValueError
        with self.assertRaises(ValueError):
            restore_cancelled_project(self.project, actor=self.accountant, comment="بازگشت")

        # Success by manager
        restore_cancelled_project(self.project, actor=self.manager, comment="برگشت از لغو", restore_invoice=False)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.IN_PROGRESS)

    def test_held_project_ids(self):
        self.assertNotIn(self.project.id, held_project_ids())
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        self.assertIn(self.project.id, held_project_ids())

        resume_suspended_stage(self.stage, actor=self.manager, comment="بازگشت")
        self.assertNotIn(self.project.id, held_project_ids())

        suspend_stage(self.stage, actor=self.manager, comment="تعلیق مجدد")
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        self.assertIn(self.project.id, held_project_ids())
