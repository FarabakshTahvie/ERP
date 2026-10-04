from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import PeriodLock, Party, Specialty
from dashboard import services
from finance import accounting
from finance.models import Invoice, Payment
from projects.models import (
    Project, ProjectStage, StageApproval, StageEvent, WorkflowStepTemplate, WorkflowTemplate,
)


class DashboardAccessTests(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="d_m", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="d_a", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        self.tech = mk(username="d_t", password="pw", role=User.Role.EMPLOYEE)
        self.client_user = mk(username="d_c", password="pw", role=User.Role.CLIENT)

    def test_manager_gets_dashboard_at_home_and_manager_url(self):
        c = Client(); c.force_login(self.manager)
        for url in (reverse("home"), reverse("dashboard:overview")):
            resp = c.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertTemplateUsed(resp, "dashboard/overview.html")

    def test_others_get_404_and_anonymous_redirects(self):
        c = Client()
        for user in (self.accountant, self.tech, self.client_user):
            c.force_login(user)
            self.assertEqual(c.get(reverse("dashboard:overview")).status_code, 404, user.username)
            self.assertEqual(c.get(reverse("dashboard:projects_table")).status_code, 404, user.username)
        c.logout()
        self.assertEqual(c.get(reverse("dashboard:overview")).status_code, 302)

    def test_accountant_home_is_not_the_manager_dashboard(self):
        c = Client(); c.force_login(self.accountant)
        self.assertTemplateNotUsed(c.get(reverse("home")), "dashboard/overview.html")

    def test_projects_table_endpoint_for_manager(self):
        c = Client(); c.force_login(self.manager)
        self.assertEqual(c.get(reverse("dashboard:projects_table")).status_code, 200)


class AttentionQueueTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک داشبورد", is_partner=True, phone_number="09125550001")
        tpl = WorkflowTemplate.objects.create(name="قالب داشبورد")
        self.step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="مرحله")
        self.step_pay = WorkflowStepTemplate.objects.create(
            template=tpl, order=2, title="تایید و پرداخت", requires_payment_selection=True)
        self.project = Project.objects.create(name="پروژه داشبورد", partner=self.partner, workflow_template=tpl,
                                              status=Project.Status.IN_PROGRESS)
        self.user = User.objects.create_user(username="dash_u", password="pw", role=User.Role.EMPLOYEE)

    def stage(self, status, order=1, step=None, **kw):
        return ProjectStage.objects.create(project=self.project, step_template=step or self.step, order=order,
                                           title=f"مرحله {order}", status=status, **kw)

    def items(self):
        return {i["key"]: i for i in services.attention_items(accounting.accounting_overview("this_month"))}

    def test_unassigned_until_someone_is_responsible(self):
        st = self.stage(ProjectStage.Status.IN_PROGRESS, started_at=timezone.now())
        self.assertEqual(self.items()["unassigned"]["count"], 1)
        st.candidate_users.add(self.user)
        self.assertNotIn("unassigned", self.items())
        st.candidate_users.clear()
        st.assigned_to = self.user
        st.save()
        self.assertNotIn("unassigned", self.items())

    def test_stale_counts_only_assigned_and_resets_on_event(self):
        old = timezone.now() - timedelta(days=5)
        st = self.stage(ProjectStage.Status.IN_PROGRESS, started_at=old)
        self.assertNotIn("stale", self.items())            # بدون مسئول ← فقط در «بدون مسئول»
        st.assigned_to = self.user
        st.save()
        self.assertEqual(self.items()["stale"]["count"], 1)
        StageEvent.objects.create(stage=st, to_status="in_progress", comment="حرکت")
        self.assertNotIn("stale", self.items())

    def test_suspended(self):
        self.stage(ProjectStage.Status.SUSPENDED, started_at=timezone.now())
        self.assertEqual(self.items()["suspended"]["count"], 1)

    def test_cancelled_project_is_ignored(self):
        self.stage(ProjectStage.Status.SUSPENDED, started_at=timezone.now())
        Project.objects.filter(pk=self.project.pk).update(status=Project.Status.CANCELLED)
        self.assertNotIn("suspended", self.items())

    def test_slow_customer_approval(self):
        st = self.stage(ProjectStage.Status.WAITING_APPROVAL, started_at=timezone.now())
        approval = StageApproval.objects.create(stage=st, sent_to_party=self.partner)
        self.assertNotIn("slow_approval", self.items())
        StageApproval.objects.filter(pk=approval.pk).update(sent_at=timezone.now() - timedelta(days=3))
        self.assertEqual(self.items()["slow_approval"]["count"], 1)

    def test_overdue_needs_confirmation_remaining_and_age(self):
        inv = Invoice.objects.create(project=self.project, number="INV-D-1", billed_party=self.partner,
                                     total_amount=Decimal("1000"), issue_date=timezone.localdate() - timedelta(days=40))
        self.assertNotIn("overdue", self.items())           # پیش‌فاکتورِ تاییدنشده
        self.stage(ProjectStage.Status.DONE, order=2, step=self.step_pay)
        self.assertEqual(self.items()["overdue"]["count"], 1)
        inv.due_date = timezone.localdate() + timedelta(days=5)
        inv.save()
        self.assertNotIn("overdue", self.items())           # هنوز سررسید نشده
        inv.due_date = None
        inv.paid_amount = Decimal("1000")
        inv.status = Invoice.Status.PAID
        inv.save()
        self.assertNotIn("overdue", self.items())           # تسویه

    def test_pending_payments_count(self):
        inv = Invoice.objects.create(project=self.project, number="INV-D-2", billed_party=self.partner,
                                     total_amount=Decimal("1000"), issue_date=timezone.localdate())
        Payment.objects.create(invoice=inv, method=Payment.Method.CARD_TO_CARD, amount=100, claimed_amount=100,
                               reference_number="R")
        self.assertEqual(self.items()["payments"]["count"], 1)

    def test_previous_month_reminder(self):
        with mock.patch("django.utils.timezone.localdate", return_value=date(2026, 10, 10)):   # ۱۴۰۵/۰۷/۱۸
            self.assertIn("previous_month", self.items())
            PeriodLock.objects.create(year=1405, month=6, is_locked=True)
            self.assertNotIn("previous_month", self.items())
        PeriodLock.objects.all().delete()
        with mock.patch("django.utils.timezone.localdate", return_value=date(2026, 9, 25)):    # ۱۴۰۵/۰۷/۰۲
            self.assertNotIn("previous_month", self.items())

    def test_levels_sorted_errors_first(self):
        self.stage(ProjectStage.Status.SUSPENDED, started_at=timezone.now())
        self.stage(ProjectStage.Status.IN_PROGRESS, order=2, started_at=timezone.now())
        ranks = [i["level"] for i in services.attention_items(accounting.accounting_overview("this_month"))]
        self.assertEqual(ranks, sorted(ranks, key=lambda l: {"error": 0, "warning": 1, "info": 2}[l]))
