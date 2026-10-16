from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance import accounting
from finance.reports import generate_periodic_financial_report
from finance.models import ChequeEvent, Invoice, Payment
from finance.services import (
    approve_payment, cancel_invoice, counted_payments, set_cheque_status, update_cheque_info,
)
from projects.models import Project
from utils.test_helpers import make_accountant

CN = "1234567890123456"
CS = Payment.ChequeStatus


class ChequeBase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="ch_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("ch_acc")
        self.tech = User.objects.create_user(username="ch_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری چک", is_client=True, phone_number="09127771001")
        self.project = Project.objects.create(name="پروژه چک", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-CH-1", billed_party=self.party,
                                              total_amount=Decimal("1000000"), issue_date=timezone.localdate(),
                                              status=Invoice.Status.SENT)
        self.future = timezone.localdate() + timedelta(days=30)

    def pending(self, amount=400000):
        return Payment.objects.create(invoice=self.invoice, method=Payment.Method.CHEQUE, amount=amount,
                                      claimed_amount=amount)

    def approved(self, amount=400000, number=CN, due=None):
        return approve_payment(self.pending(amount), approved_by=self.accountant, verified_amount=str(amount),
                               cheque_number=number, cheque_bank="ملی", cheque_due_date=due or self.future)

    def paid(self):
        self.invoice.refresh_from_db()
        return self.invoice.paid_amount

    def test_bounce_removes_the_money_everywhere_and_reopens_invoice(self):
        p = self.approved(amount=1000000)
        day = timezone.localdate()
        span = (day - timedelta(days=1), day + timedelta(days=1))
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.status, self.invoice.paid_amount), (Invoice.Status.PAID, Decimal("1000000")))
        self.assertEqual(accounting.accounting_overview("all")["collected"], Decimal("1000000"))
        self.assertEqual(generate_periodic_financial_report(*span)["total_received"], Decimal("1000000"))
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت خورد")
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.status, self.invoice.paid_amount), (Invoice.Status.SENT, Decimal("0")))
        self.assertIsNone(self.invoice.settled_at)
        self.assertEqual(accounting.accounting_overview("all")["collected"], Decimal("0"))
        self.assertEqual(generate_periodic_financial_report(*span)["total_received"], Decimal("0"))
        self.assertFalse(counted_payments(Payment.objects.all()).exists())


class ChequeApproveTests(ChequeBase):
    def test_needs_sayyadi_and_due_date_and_changes_nothing_on_error(self):
        p = self.pending()
        for kw in (dict(cheque_number="123", cheque_due_date=self.future),
                   dict(cheque_number="a" * 16, cheque_due_date=self.future),
                   dict(cheque_number=CN, cheque_due_date=None)):
            with self.assertRaises(ValueError, msg=str(kw)):
                approve_payment(p, approved_by=self.accountant, verified_amount="400000", **kw)
        p.refresh_from_db()
        self.assertEqual((p.status, p.cheque_status), (Payment.Status.PENDING, ""))
        self.assertEqual(self.paid(), 0)

    def test_approve_marks_received_counts_money_and_logs(self):
        p = self.approved(number="۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶")
        self.assertEqual((p.cheque_status, p.cheque_number, p.cheque_due_date), (CS.RECEIVED, CN, self.future))
        self.assertEqual(self.paid(), Decimal("400000"))
        ev = ChequeEvent.objects.get(payment=p)
        self.assertEqual((ev.from_status, ev.to_status, ev.actor), ("", "received", self.accountant))
