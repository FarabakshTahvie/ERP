import jdatetime
from datetime import timedelta
from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Service
from core.models import PeriodLock, Party, Specialty
from core.periods import jalali_ym
from finance import accounting
from finance.aging import get_customer_aging_data
from finance.models import AccountingEvent, Invoice, Payment
from finance.services import approve_payment, cancel_invoice, create_customer_payment, restore_invoice, set_invoice_due_date
from projects.models import Project, ProjectStage
from projects.proforma import issue_proforma, save_proforma
from projects.services import advance_stage, create_project_from_technician_intake
from projects.workflow_v2 import build_workflow_v2


class InvoiceBase(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="i_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="i_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        self.tech = mk(username="i_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری فاکتور", is_client=True, phone_number="09126661001")
        self.project = Project.objects.create(name="پروژه فاکتور", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.today = timezone.localdate()
        self.invoice = Invoice.objects.create(project=self.project, number="INV-I-1", billed_party=self.party,
                                              total_amount=Decimal("1000"), issue_date=self.today,
                                              status=Invoice.Status.SENT)

    def pay(self, status=Payment.Status.PENDING, method=Payment.Method.CARD_TO_CARD):
        return Payment.objects.create(invoice=self.invoice, method=method, amount=100, claimed_amount=100,
                                      status=status, reference_number="R")


class CancelInvoiceTests(InvoiceBase):
    def test_cancel_removes_invoice_from_sales_and_logs(self):
        cancel_invoice(invoice=self.invoice, reason="مشتری منصرف شد", actor=self.manager)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.CANCELLED)
        stats = accounting.accounting_overview("all")
        self.assertEqual(stats["sales"], Decimal("0"))
        self.assertEqual(stats["receivable"], Decimal("0"))
        self.assertTrue(AccountingEvent.objects.filter(project=self.project, text__contains="لغو شد").exists())

    def test_only_manager_with_reason(self):
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                cancel_invoice(invoice=self.invoice, reason="دلیل", actor=actor)
        with self.assertRaises(ValueError):
            cancel_invoice(invoice=self.invoice, reason=" ", actor=self.manager)

    def test_blocked_by_approved_real_payment_but_not_by_credit(self):
        self.pay(Payment.Status.APPROVED, Payment.Method.CREDIT)
        cancel_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)   # اعتباری مانع نیست

    def test_blocked_by_approved_real_payment(self):
        self.pay(Payment.Status.APPROVED)
        with self.assertRaises(ValueError) as ctx:
            cancel_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)
        self.assertIn("پرداخت تاییدشده", str(ctx.exception))
        self.invoice.refresh_from_db()
        self.assertNotEqual(self.invoice.status, Invoice.Status.CANCELLED)

    def test_pending_payments_are_auto_rejected(self):
        pending = self.pay()
        cancel_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Payment.Status.REJECTED)
        self.assertEqual(pending.rejection_reason, "فاکتور لغو شد")

    def test_already_cancelled_and_locked_month(self):
        cancel_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)
        with self.assertRaises(ValueError):
            cancel_invoice(invoice=self.invoice, reason="دوباره", actor=self.manager)
        inv2_project = Project.objects.create(name="پروژه دوم", partner=self.party, status=Project.Status.IN_PROGRESS)
        inv2 = Invoice.objects.create(project=inv2_project, number="INV-I-2", billed_party=self.party,
                                      total_amount=Decimal("500"), issue_date=self.today)
        y, m = jalali_ym(self.today)
        PeriodLock.objects.create(year=y, month=m, is_locked=True)
        with self.assertRaises(ValueError) as ctx:
            cancel_invoice(invoice=inv2, reason="دلیل", actor=self.manager)
        self.assertIn("بسته شده", str(ctx.exception))

    def test_restore_invoice(self):
        # فقط مدیر، دلیل اجباری، فقط فاکتور لغو‌شده، ماه بسته خطا می‌دهد، paid_amount بازمحاسبه می‌شود
        # 1. Non-manager fails
        self.invoice.status = Invoice.Status.CANCELLED
        self.invoice.save()
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                restore_invoice(invoice=self.invoice, reason="دلیل", actor=actor)

        # 2. Reason required
        with self.assertRaises(ValueError):
            restore_invoice(invoice=self.invoice, reason=" ", actor=self.manager)

        # 3. Only cancelled invoice
        self.invoice.status = Invoice.Status.SENT
        self.invoice.save()
        with self.assertRaises(ValueError):
            restore_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)

        # 4. Locked month fails
        self.invoice.status = Invoice.Status.CANCELLED
        self.invoice.save()
        y, m = jalali_ym(self.today)
        PeriodLock.objects.create(year=y, month=m, is_locked=True)
        with self.assertRaises(ValueError) as ctx:
            restore_invoice(invoice=self.invoice, reason="دلیل", actor=self.manager)
        self.assertIn("بسته شده", str(ctx.exception))
        PeriodLock.objects.filter(year=y, month=m).delete()

        # 5. Success and paid_amount recalculated
        restored = restore_invoice(invoice=self.invoice, reason="برگشت فاکتور", actor=self.manager)
        self.assertEqual(restored.status, Invoice.Status.SENT)
        self.assertEqual(restored.paid_amount, Decimal("0"))
        self.assertTrue(AccountingEvent.objects.filter(project=self.project, text__contains="برگردانده شد").exists())

    def test_cancelled_invoice_refuses_approve_and_new_customer_payment(self):
        pending = self.pay()
        Invoice.objects.filter(pk=self.invoice.pk).update(status=Invoice.Status.CANCELLED)
        with self.assertRaises(ValueError):
            approve_payment(pending, approved_by=self.manager, verified_amount="100")
        self.invoice.refresh_from_db()
        with self.assertRaises(ValueError):
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تسویه")


class DueDateTests(InvoiceBase):
    def test_set_clear_and_aging(self):
        from utils.test_helpers import confirm_invoice
        confirm_invoice(self.invoice)
        Invoice.objects.filter(pk=self.invoice.pk).update(issue_date=self.today - timedelta(days=40))
        _, rows = get_customer_aging_data(self.party)
        self.assertEqual(rows[0]["bucket"], "31-60")
        due = self.today + timedelta(days=10)
        set_invoice_due_date(invoice=self.invoice, due_date=due, actor=self.accountant)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.due_date, due)
        _, rows = get_customer_aging_data(self.party)
        self.assertEqual(rows[0]["bucket"], "current")
        set_invoice_due_date(invoice=self.invoice, due_date=None, actor=self.manager)
        self.invoice.refresh_from_db()
        self.assertIsNone(self.invoice.due_date)

    def test_guards(self):
        with self.assertRaises(ValueError):
            set_invoice_due_date(invoice=self.invoice, due_date=self.today, actor=self.tech)
        with self.assertRaises(ValueError):
            set_invoice_due_date(invoice=self.invoice, due_date=self.today - timedelta(days=1), actor=self.accountant)
        Invoice.objects.filter(pk=self.invoice.pk).update(status=Invoice.Status.CANCELLED)
        with self.assertRaises(ValueError):
            set_invoice_due_date(invoice=self.invoice, due_date=self.today, actor=self.accountant)


class InvoiceControlViewsTests(InvoiceBase):
    def test_due_view(self):
        shamsi = jdatetime.date.fromgregorian(date=self.today + timedelta(days=5)).strftime("%Y/%m/%d")
        c = Client(); c.force_login(self.accountant)
        r = c.post(reverse("finance:accounting_set_due", args=[self.project.id]), {"due_date": shamsi})
        self.assertEqual(r.status_code, 302)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.due_date, self.today + timedelta(days=5))

    def test_cancel_view_manager_only(self):
        url = reverse("finance:accounting_cancel_invoice", args=[self.project.id])
        c = Client()
        c.force_login(self.accountant)
        c.post(url, {"reason": "دلیل"})
        self.invoice.refresh_from_db()
        self.assertNotEqual(self.invoice.status, Invoice.Status.CANCELLED)
        c.force_login(self.tech)
        self.assertEqual(c.post(url, {"reason": "دلیل"}).status_code, 302)
        c.force_login(self.manager)
        c.post(url, {"reason": "دلیل"})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.CANCELLED)

    def test_project_file_shows_cancel_form_only_to_manager(self):
        url = reverse("finance:accounting_project", args=[self.project.id])
        c = Client()
        c.force_login(self.manager)
        self.assertContains(c.get(url), "لغو فاکتور")
        c.force_login(self.accountant)
        self.assertNotContains(c.get(url), "لغو فاکتور")
        self.assertContains(c.get(url), "ثبت سررسید")


class ProformaIssueSentTests(TestCase):
    def test_issued_proforma_is_marked_sent(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        partner = Party.objects.create(name="شریک ارسال", is_partner=True, phone_number="09127771111")
        acc = User.objects.create_user(username="sent_acc", password="pw", role=User.Role.EMPLOYEE)
        acc.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        service = Service.objects.create(name="خدمت ارسال")
        build_workflow_v2(make_default=True)
        project, _, _ = create_project_from_technician_intake(
            created_by=acc, party_id=partner.id, visit_date=timezone.localdate(), issue_proforma=False)
        advance_stage(project.stages.first(), actor=acc, new_status=ProjectStage.Status.DONE, comment="بازدید شد")
        rows = [{"pk": None, "service_id": service.id, "qty": Decimal("1"),
                 "unit_price": Decimal("1000000"), "materials": []}]
        save_proforma(project=project, actor=acc, service_rows=rows)
        invoice, _ = issue_proforma(project=project, actor=acc)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.SENT)
