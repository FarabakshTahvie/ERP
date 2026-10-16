from datetime import timedelta
from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import PeriodLock, Party, Specialty
from core.periods import current_ym, month_label
from finance.models import Invoice, Payment
from projects.models import (
    Project, ProjectStage, StageApproval, StageEvent, StageKind, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.services import assign_stage, cancel_project_from_stage, resume_suspended_stage


def SPEC(name):
    return Specialty.objects.get_or_create(name=name)[0]


class ControlBase(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="c_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="c_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(SPEC("حسابدار"))
        self.tech = mk(username="c_tech", password="pw", role=User.Role.EMPLOYEE)
        self.tech.specialties.add(SPEC("کانال‌کش"))
        self.other = mk(username="c_other", password="pw", role=User.Role.EMPLOYEE)
        self.inactive = mk(username="c_off", password="pw", role=User.Role.EMPLOYEE, is_active=False)
        self.client_user = mk(username="c_cli", password="pw", role=User.Role.CLIENT)
        self.partner = Party.objects.create(name="شریک کنترل", is_partner=True, phone_number="09125551001")
        self.tpl = WorkflowTemplate.objects.create(name="قالب کنترل")
        self.step = WorkflowStepTemplate.objects.create(
            template=self.tpl, order=1, title="برش", responsible_specialty=SPEC("کانال‌کش"))
        self.step_pay = WorkflowStepTemplate.objects.create(
            template=self.tpl, order=2, title="تایید مشتری",
            approval_by=WorkflowStepTemplate.ApprovalBy.PARTNER, requires_payment_selection=True)
        self.project = Project.objects.create(name="پروژه کنترل", partner=self.partner, workflow_template=self.tpl,
                                              status=Project.Status.IN_PROGRESS)

    def stage(self, status=ProjectStage.Status.IN_PROGRESS, *, order=1, step=None, project=None,
              kind=StageKind.GENERIC, **kw):
        return ProjectStage.objects.create(
            project=project or self.project, step_template=step or self.step, order=order,
            title=f"مرحله {order}", kind=kind, status=status, started_at=timezone.now(), **kw)

    def invoice(self, project=None):
        return Invoice.objects.create(project=project or self.project, number="INV-C-1", billed_party=self.partner,
                                      total_amount=Decimal("1000"), issue_date=timezone.localdate())


class AssignStageTests(ControlBase):
    def test_requires_reason_and_manager(self):
        st = self.stage()
        with self.assertRaises(ValueError):
            assign_stage(st, self.tech, self.manager, "  ")
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                assign_stage(st, self.other, actor, "دلیل")
        st.refresh_from_db()
        self.assertIsNone(st.assigned_to)

    def test_only_in_progress_stage_of_live_project(self):
        for status in (ProjectStage.Status.PENDING, ProjectStage.Status.DONE, ProjectStage.Status.SUSPENDED):
            st = self.stage(status, order=5)
            with self.assertRaises(ValueError):
                assign_stage(st, self.tech, self.manager, "دلیل")
        st = self.stage(order=6)
        Project.objects.filter(pk=self.project.pk).update(status=Project.Status.CANCELLED)
        with self.assertRaises(ValueError):
            assign_stage(st, self.tech, self.manager, "دلیل")

    def test_money_stages_only_to_accountant(self):
        for kind in (StageKind.PROFORMA, StageKind.FINAL_REVIEW):
            st = self.stage(kind=kind, order=7)
            with self.assertRaises(ValueError):
                assign_stage(st, self.tech, self.manager, "دلیل")
            assign_stage(st, self.accountant, self.manager, "دلیل")
            st.refresh_from_db()
            self.assertEqual(st.assigned_to, self.accountant)


class ResumeAndCancelTests(ControlBase):
    def test_resume_guards(self):
        live = self.stage()
        with self.assertRaises(ValueError):
            resume_suspended_stage(live, self.manager, "دلیل")
        sus = self.stage(ProjectStage.Status.SUSPENDED, order=3)
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                resume_suspended_stage(sus, actor, "دلیل")
        with self.assertRaises(ValueError):
            resume_suspended_stage(sus, self.manager, "")

    def test_cancel_project_cancels_pending_approvals(self):
        waiting = self.stage(ProjectStage.Status.WAITING_APPROVAL, order=2, step=self.step_pay)
        approval = StageApproval.objects.create(stage=waiting, sent_to_party=self.partner)
        sus = self.stage(ProjectStage.Status.SUSPENDED, order=3)
        cancel_project_from_stage(sus, self.manager, "منصرف شد")
        self.project.refresh_from_db()
        approval.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)
        self.assertEqual(approval.decision, StageApproval.Decision.CANCELLED)

    def test_cancel_project_with_invoice_flag(self):
        inv = self.invoice()
        sus = self.stage(ProjectStage.Status.SUSPENDED)
        cancel_project_from_stage(sus, self.manager, "منصرف شد", cancel_invoice=True)
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

    def test_cancel_project_rolls_back_when_invoice_has_real_payment(self):
        inv = self.invoice()
        Payment.objects.create(invoice=inv, method=Payment.Method.CARD_TO_CARD, amount=100, claimed_amount=100,
                               status=Payment.Status.APPROVED, reference_number="R")
        sus = self.stage(ProjectStage.Status.SUSPENDED)
        with self.assertRaises(ValueError):
            cancel_project_from_stage(sus, self.manager, "منصرف شد", cancel_invoice=True)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.IN_PROGRESS)


class ControlViewsTests(ControlBase):
    def test_non_manager_post_changes_nothing(self):
        s = self.stage()
        c = Client(); c.force_login(self.tech)
        r = c.post(reverse("dashboard:assign_stage", args=[s.id]), {"target_user": self.tech.id, "comment": "x"})
        self.assertEqual(r.status_code, 404)
        s.refresh_from_db(); self.assertIsNone(s.assigned_to)

    def test_accountant_cannot_resume_or_cancel_via_views(self):
        s = self.stage(ProjectStage.Status.SUSPENDED)
        c = Client(); c.force_login(self.accountant)
        for name in ("dashboard:suspended_resume", "dashboard:suspended_cancel"):
            self.assertEqual(c.post(reverse(name, args=[s.id]), {"comment": "x"}).status_code, 404)
