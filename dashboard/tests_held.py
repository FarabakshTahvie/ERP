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
