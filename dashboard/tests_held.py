from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party, Specialty
from finance import accounting
from finance.models import Invoice
from projects.models import Project, ProjectStage, StageKind, WorkflowStepTemplate, WorkflowTemplate
from projects.services import cancel_project_from_stage, suspend_stage


def SPEC(name):
    return Specialty.objects.get_or_create(name=name)[0]


class HeldDashboardTests(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="dh_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="dh_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(SPEC("حسابدار"))

        self.partner = Party.objects.create(name="شریک تست", is_partner=True, phone_number="09123334455")
        self.client_party = Party.objects.create(name="مشتری تست", is_client=True, phone_number="09123334456")
        self.tpl = WorkflowTemplate.objects.create(name="قالب تست")
        self.step_fr = WorkflowStepTemplate.objects.create(template=self.tpl, order=10, title="بازبینی نهایی", kind=StageKind.FINAL_REVIEW)

        self.project = Project.objects.create(
            name="پروژه تست", partner=self.partner, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS
        )
        self.stage = ProjectStage.objects.create(
            project=self.project, step_template=self.step_fr, order=10, title="بازبینی نهایی", kind=StageKind.FINAL_REVIEW, status=ProjectStage.Status.IN_PROGRESS
        )

    def test_accountant_access_and_restrictions(self):
        # Accountant can view suspended_page and held_detail (they have view permission or accountant specialty)
        # But cannot resume, cancel, suspend, or restore
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")

        c = Client()
        c.force_login(self.accountant)

        # Access to suspended_page (view only)
        r_page = c.get(reverse("dashboard:suspended"))
        self.assertEqual(r_page.status_code, 200)

        # Access to held_detail (view only)
        r_detail = c.get(reverse("dashboard:held_detail", args=[self.project.id]))
        self.assertEqual(r_detail.status_code, 200)

        # Attempt to resume -> fails with 404 because accountant doesn't have assign capabilities
        r_resume = c.post(reverse("dashboard:suspended_resume", args=[self.stage.id]), {"comment": "حسابدار برگرداند"})
        self.assertEqual(r_resume.status_code, 404)

        # Attempt to cancel -> fails with 404
        r_cancel = c.post(reverse("dashboard:suspended_cancel", args=[self.stage.id]), {"comment": "حسابدار لغو کند"})
        self.assertEqual(r_cancel.status_code, 404)

        # Attempt to restore -> fails with 404
        r_restore = c.post(reverse("dashboard:project_restore", args=[self.project.id]), {"comment": "حسابدار برگرداند از لغو"})
        self.assertEqual(r_restore.status_code, 404)

    def test_manager_actions_and_next_redirect(self):
        # Manager can perform all actions
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")

        c = Client()
        c.force_login(self.manager)

        # Resume with custom next
        next_url = reverse("dashboard:held_detail", args=[self.project.id])
        r = c.post(reverse("dashboard:suspended_resume", args=[self.stage.id]), {"comment": "تایید مدیر", "next": next_url})
        # After resuming the last suspended stage, the project is no longer held (no suspended stages),
        # so held_detail would return 404. Checking status_code 302 and target redirect.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, next_url)

        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.IN_PROGRESS)

    def test_receivable_identity_with_customer_center(self):
        # سناریوها: فاکتور تاییدشده‌ی عادی، روی پروژه‌ی معلق، روی پروژه‌ی لغوشده (فاکتور لغو نشده)،
        # پیش‌فاکتور تاییدنشده، و فاکتور با پرداخت جزئی
        from utils.test_helpers import confirm_invoice
        from projects.services import suspend_stage, cancel_project_from_stage

        # ۱. فاکتور تاییدشده عادی
        p1 = Project.objects.create(name="پروژه ۱", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        s1 = ProjectStage.objects.create(project=p1, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv1 = Invoice.objects.create(number="INV-ID-1", billed_party=self.client_party, project=p1, status=Invoice.Status.SENT, total_amount=Decimal("1000"), issue_date=timezone.localdate())
        confirm_invoice(inv1)

        # ۲. روی پروژه معلق
        p2 = Project.objects.create(name="پروژه ۲", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        s2 = ProjectStage.objects.create(project=p2, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv2 = Invoice.objects.create(number="INV-ID-2", billed_party=self.client_party, project=p2, status=Invoice.Status.SENT, total_amount=Decimal("2000"), issue_date=timezone.localdate())
        confirm_invoice(inv2)
        suspend_stage(s2, actor=self.manager, comment="تعلیق")

        # ۳. روی پروژه لغوشده (فاکتور لغو نشده)
        p3 = Project.objects.create(name="پروژه ۳", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        s3 = ProjectStage.objects.create(project=p3, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv3 = Invoice.objects.create(number="INV-ID-3", billed_party=self.client_party, project=p3, status=Invoice.Status.SENT, total_amount=Decimal("3000"), issue_date=timezone.localdate())
        confirm_invoice(inv3)
        cancel_project_from_stage(s3, actor=self.manager, comment="لغو", cancel_invoice=False)

        # ۴. پیش‌فاکتور تاییدنشده
        p4 = Project.objects.create(name="پروژه ۴", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        s4 = ProjectStage.objects.create(project=p4, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv4 = Invoice.objects.create(number="INV-ID-4", billed_party=self.client_party, project=p4, status=Invoice.Status.SENT, total_amount=Decimal("4000"), issue_date=timezone.localdate())

        # ۵. فاکتور با پرداخت جزئی
        p5 = Project.objects.create(name="پروژه ۵", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        s5 = ProjectStage.objects.create(project=p5, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv5 = Invoice.objects.create(number="INV-ID-5", billed_party=self.client_party, project=p5, status=Invoice.Status.SENT, total_amount=Decimal("5000"), paid_amount=Decimal("1500"), issue_date=timezone.localdate())

        total = sum((p.total_outstanding for p in Party.objects.all()), Decimal("0"))
        s = accounting.accounting_overview("all")
        self.assertEqual(s["receivable"] + s["held_receivable"], total)

    def test_overdue_invoices_excludes_held_project(self):
        from utils.test_helpers import confirm_invoice
        from projects.services import suspend_stage
        from dashboard.services import overdue_invoices
        from datetime import timedelta
        p = Project.objects.create(name="پروژه معوق", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        st = ProjectStage.objects.create(project=p, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv = Invoice.objects.create(number="INV-OD-1", billed_party=self.client_party, project=p, status=Invoice.Status.SENT, total_amount=Decimal("1000"), issue_date=timezone.localdate() - timedelta(days=60))
        confirm_invoice(inv)
        
        today = timezone.localdate()
        self.assertIn(inv, overdue_invoices(today))
        suspend_stage(st, actor=self.manager, comment="تعلیق")
        self.assertNotIn(inv, overdue_invoices(today))

    def test_party_total_outstanding_unaffected_by_suspend_and_cancel(self):
        from utils.test_helpers import confirm_invoice
        from projects.services import suspend_stage, cancel_project_from_stage
        p = Project.objects.create(name="پروژه طلب", partner=self.partner, owner=self.client_party, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS)
        st = ProjectStage.objects.create(project=p, step_template=self.step_fr, order=10, title="تایید", status=ProjectStage.Status.IN_PROGRESS)
        inv = Invoice.objects.create(number="INV-TO-1", billed_party=self.client_party, project=p, status=Invoice.Status.SENT, total_amount=Decimal("1000"), issue_date=timezone.localdate())
        confirm_invoice(inv)

        initial_out = self.client_party.total_outstanding
        suspend_stage(st, actor=self.manager, comment="تعلیق")
        self.assertEqual(self.client_party.total_outstanding, initial_out)

        cancel_project_from_stage(st, actor=self.manager, comment="لغو", cancel_invoice=False)
        self.assertEqual(self.client_party.total_outstanding, initial_out)

    def test_held_detail_non_held_raises_404(self):
        c = Client()
        c.force_login(self.manager)
        # self.project is IN_PROGRESS without suspended stages
        resp = c.get(reverse("dashboard:held_detail", args=[self.project.id]))
        self.assertEqual(resp.status_code, 404)

    def test_tables_search_and_sort(self):
        c = Client()
        c.force_login(self.manager)
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        Invoice.objects.create(project=self.project, number="INV-1000", billed_party=self.partner, total_amount=Decimal("1000"), issue_date=timezone.localdate())

        # Suspended table search & sort
        r1 = c.get(reverse("dashboard:suspended_table"), {"hs_q": "تست", "hs_sort": "revenue", "hs_dir": "desc"})
        self.assertEqual(r1.status_code, 200)
        self.assertContains(r1, "۱,۰۰۰")  # Persian digits and separated

        # Cancelled table search & sort
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        r2 = c.get(reverse("dashboard:cancelled_table"), {"hc_q": "تست", "hc_sort": "revenue", "hc_dir": "desc"})
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, "۱,۰۰۰")

    def test_final_review_post_manager_vs_accountant_and_cancel_button(self):
        c = Client()
        # Stage is suspended
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        
        # Accountant POST to suspend / cancel -> 404
        c.force_login(self.accountant)
        r_acc_sus = c.post(reverse("dashboard:stage_suspend", args=[self.stage.id]), {"comment": "تعلیق"})
        self.assertEqual(r_acc_sus.status_code, 404)
        r_acc_can = c.post(reverse("dashboard:suspended_cancel", args=[self.stage.id]), {"comment": "لغو"})
        self.assertEqual(r_acc_can.status_code, 404)

        # Final review page for accountant on cancelled project doesn't have approve button
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        resp = c.get(reverse("projects:final_review", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "تایید و تسویه")

    def test_cancelled_project_in_accounting_projects_table(self):
        c = Client()
        c.force_login(self.accountant)
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")
        cancel_project_from_stage(self.stage, actor=self.manager, comment="لغو")
        resp = c.get(reverse("finance:accounting_projects_table"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.project.name)
