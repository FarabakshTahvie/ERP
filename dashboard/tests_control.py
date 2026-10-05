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
    def test_same_specialty_assign_clears_pool_and_logs(self):
        st = self.stage()
        st.candidate_users.add(self.other)
        assign_stage(st, self.tech, self.manager, "تیم کم‌نفر است")
        st.refresh_from_db()
        self.assertEqual(st.assigned_to, self.tech)
        self.assertEqual(st.candidate_users.count(), 0)
        ev = StageEvent.objects.filter(stage=st).latest("created_at")
        self.assertIn("تیم کم‌نفر است", ev.comment)
        self.assertNotIn("خارج از تخصص", ev.comment)

    def test_off_specialty_allowed_and_marked(self):
        st = self.stage()
        assign_stage(st, self.other, self.manager, "فوری")
        ev = StageEvent.objects.filter(stage=st).latest("created_at")
        self.assertIn("خارج از تخصص", ev.comment)

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

    def test_target_must_be_active_employee_and_different(self):
        st = self.stage()
        for bad in (self.inactive, self.client_user, None):
            with self.assertRaises(ValueError):
                assign_stage(st, bad, self.manager, "دلیل")
        assign_stage(st, self.tech, self.manager, "دلیل")
        with self.assertRaises(ValueError):
            assign_stage(st, self.tech, self.manager, "دوباره")

    def test_money_stages_only_to_accountant(self):
        for kind in (StageKind.PROFORMA, StageKind.FINAL_REVIEW):
            st = self.stage(kind=kind, order=7)
            with self.assertRaises(ValueError):
                assign_stage(st, self.tech, self.manager, "دلیل")
            assign_stage(st, self.accountant, self.manager, "دلیل")
            st.refresh_from_db()
            self.assertEqual(st.assigned_to, self.accountant)


class ResumeAndCancelTests(ControlBase):
    def test_resume_plain_stage_goes_in_progress_keeping_owner(self):
        st = self.stage(ProjectStage.Status.SUSPENDED, assigned_to=self.tech)
        resume_suspended_stage(st, self.manager, "بررسی شد")
        st.refresh_from_db()
        self.assertEqual(st.status, ProjectStage.Status.IN_PROGRESS)
        self.assertEqual(st.assigned_to, self.tech)

    def test_resume_customer_approval_stage_resends_to_customer(self):
        st = self.stage(ProjectStage.Status.SUSPENDED, order=2, step=self.step_pay)
        resume_suspended_stage(st, self.manager, "مشتری موافقت کرد")
        st.refresh_from_db()
        self.assertEqual(st.status, ProjectStage.Status.WAITING_APPROVAL)
        self.assertTrue(st.approvals.filter(decision=StageApproval.Decision.PENDING).exists())

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

    def test_cancel_project_cancels_open_part_requests(self):
        from catalog.models import Item
        from projects.models import PartRequest
        item = Item.objects.create(name="قطعه لغو", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        sus = self.stage(ProjectStage.Status.SUSPENDED)
        req = PartRequest.objects.create(project=self.project, stage=sus, item=item, qty=1, note="x",
                                         requested_by=self.tech)
        cancel_project_from_stage(sus, self.manager, "منصرف شد")
        req.refresh_from_db()
        self.assertEqual(req.status, PartRequest.Status.CANCELLED)

    def test_cancel_project_guards(self):
        sus = self.stage(ProjectStage.Status.SUSPENDED)
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                cancel_project_from_stage(sus, actor, "دلیل")
        with self.assertRaises(ValueError):
            cancel_project_from_stage(sus, self.manager, " ")
        cancel_project_from_stage(sus, self.manager, "دلیل")
        with self.assertRaises(ValueError):
            cancel_project_from_stage(sus, self.manager, "دوباره")

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

    def test_cancelled_project_tasks_leave_technician_lists(self):
        self.stage(assigned_to=self.tech)
        c = Client(); c.force_login(self.tech)
        url = reverse("projects:dashboard_my_tasks_table")
        self.assertContains(c.get(url), "پروژه کنترل")
        Project.objects.filter(pk=self.project.pk).update(status=Project.Status.CANCELLED)
        self.assertNotContains(c.get(url), "پروژه کنترل")


class ControlViewsTests(ControlBase):
    def test_pages_manager_only(self):
        s = self.stage()
        urls = [reverse("dashboard:stages"), reverse("dashboard:stages_table"),
                reverse("dashboard:assign_stage", args=[s.id])]
        c = Client(); c.force_login(self.manager)
        for u in urls:
            self.assertEqual(c.get(u).status_code, 200, u)
        for user in (self.accountant, self.tech, self.client_user):
            c.force_login(user)
            for u in urls:
                self.assertEqual(c.get(u).status_code, 404, f"{user.username} {u}")

    def test_suspended_page_accessible_by_manager_and_accountant(self):
        url = reverse("dashboard:suspended")
        c = Client()
        for user in (self.manager, self.accountant):
            c.force_login(user)
            self.assertEqual(c.get(url).status_code, 200, f"{user.username} {url}")
        for user in (self.tech, self.client_user):
            c.force_login(user)
            self.assertEqual(c.get(url).status_code, 404, f"{user.username} {url}")

    def test_stages_table_filters_unowned(self):
        self.stage()
        other = Project.objects.create(name="پروژه دارای مسئول", partner=self.partner, workflow_template=self.tpl,
                                       status=Project.Status.IN_PROGRESS)
        self.stage(project=other, assigned_to=self.tech)
        c = Client(); c.force_login(self.manager)
        content = c.get(reverse("dashboard:stages_table"), {"ds_f_no_owner": "1"}).content.decode("utf-8")
        self.assertIn("پروژه کنترل", content)
        self.assertNotIn("پروژه دارای مسئول", content)

    def test_assign_post_flow_and_tampering(self):
        s = self.stage()
        url = reverse("dashboard:assign_stage", args=[s.id])
        c = Client(); c.force_login(self.manager)
        c.post(url, {"target_user": self.tech.id, "comment": ""})
        s.refresh_from_db(); self.assertIsNone(s.assigned_to)
        self.assertEqual(c.post(url, {"target_user": "abc", "comment": "x"}).status_code, 302)
        resp = c.post(url, {"target_user": self.tech.id, "comment": "ارجاع تست"})
        self.assertRedirects(resp, reverse("dashboard:stages"), fetch_redirect_response=False)
        s.refresh_from_db(); self.assertEqual(s.assigned_to, self.tech)

    def test_non_manager_post_changes_nothing(self):
        s = self.stage()
        c = Client(); c.force_login(self.tech)
        r = c.post(reverse("dashboard:assign_stage", args=[s.id]), {"target_user": self.tech.id, "comment": "x"})
        self.assertEqual(r.status_code, 404)
        s.refresh_from_db(); self.assertIsNone(s.assigned_to)

    def test_suspended_resume_and_cancel_views(self):
        s = self.stage(ProjectStage.Status.SUSPENDED)
        c = Client(); c.force_login(self.manager)
        self.assertContains(c.get(reverse("dashboard:suspended")), "پروژه کنترل")
        c.post(reverse("dashboard:suspended_resume", args=[s.id]), {"comment": "برگشت"})
        s.refresh_from_db(); self.assertEqual(s.status, ProjectStage.Status.IN_PROGRESS)
        s.status = ProjectStage.Status.SUSPENDED; s.save()
        inv = self.invoice()
        c.post(reverse("dashboard:suspended_cancel", args=[s.id]), {"comment": "لغو", "cancel_invoice": "on"})
        self.project.refresh_from_db(); inv.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CANCELLED)
        self.assertEqual(inv.status, Invoice.Status.CANCELLED)

    def test_accountant_cannot_resume_or_cancel_via_views(self):
        s = self.stage(ProjectStage.Status.SUSPENDED)
        c = Client(); c.force_login(self.accountant)
        for name in ("dashboard:suspended_resume", "dashboard:suspended_cancel"):
            self.assertEqual(c.post(reverse(name, args=[s.id]), {"comment": "x"}).status_code, 404)

    def test_month_lock_from_dashboard_returns_to_dashboard(self):
        y, m = current_ym(); m -= 1
        if m < 1:
            y, m = y - 1, 12
        c = Client(); c.force_login(self.manager)
        self.assertContains(c.get(reverse("dashboard:overview")), month_label(y, m))
        data = {"year": y, "month": m, "action": "lock", "next": reverse("dashboard:overview")}
        self.assertRedirects(c.post(reverse("finance:accounting_period_toggle"), data),
                             reverse("dashboard:overview"), fetch_redirect_response=False)
        self.assertTrue(PeriodLock.objects.filter(year=y, month=m, is_locked=True).exists())

    def test_external_next_is_ignored_and_accountant_cannot_unlock(self):
        y, m = current_ym(); m -= 1
        if m < 1:
            y, m = y - 1, 12
        PeriodLock.objects.create(year=y, month=m, is_locked=True)
        c = Client(); c.force_login(self.accountant)
        r = c.post(reverse("finance:accounting_period_toggle"),
                   {"year": y, "month": m, "action": "unlock", "reason": "x", "next": "https://evil.example/"})
        self.assertRedirects(r, reverse("finance:accounting_periods"), fetch_redirect_response=False)
        self.assertTrue(PeriodLock.objects.get(year=y, month=m).is_locked)
