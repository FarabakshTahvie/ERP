import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance import accounting
from finance.models import ChequeEvent, Invoice, Payment
from finance.services import (
    approve_payment, cancel_invoice, cheque_due_warning, counted_payments, set_cheque_status, update_cheque_info,
)
from projects.models import Project
from utils.test_helpers import make_accountant, make_image_file

CN = "1234567890123456"
CS = Payment.ChequeStatus


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ChequeBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

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

    def test_past_due_date_is_only_a_warning(self):
        old = timezone.localdate() - timedelta(days=20)
        self.assertEqual(self.approved(due=old).status, Payment.Status.APPROVED)
        self.assertTrue(cheque_due_warning(old))
        self.assertEqual(cheque_due_warning(self.future), "")
        self.assertEqual(cheque_due_warning(None), "")

    def test_same_cheque_twice_is_refused_until_the_first_bounces(self):
        first = self.approved(amount=300000)
        with self.assertRaises(ValueError):
            self.approved(amount=200000)
        set_cheque_status(payment=first, status=CS.BOUNCED, actor=self.accountant, note="موجودی نبود")
        self.assertEqual(self.approved(amount=200000).cheque_status, CS.RECEIVED)

    def test_card_to_card_approval_is_unchanged(self):
        p = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100,
                                   claimed_amount=100, reference_number="R")
        p = approve_payment(p, approved_by=self.accountant, verified_amount="100")
        self.assertEqual((p.status, p.cheque_status), (Payment.Status.APPROVED, ""))


class ChequeStatusTests(ChequeBase):
    def test_happy_path_and_final_states(self):
        p = self.approved()
        set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.accountant)
        p = set_cheque_status(payment=p, status=CS.COLLECTED, actor=self.manager)
        self.assertEqual(p.cheque_status, CS.COLLECTED)
        self.assertEqual(self.paid(), Decimal("400000"))
        for target in (CS.DEPOSITED, CS.RECEIVED, CS.BOUNCED):
            with self.assertRaises(ValueError):
                set_cheque_status(payment=p, status=target, actor=self.manager, note="x")
        self.assertEqual(ChequeEvent.objects.filter(payment=p).count(), 3)

    def test_invalid_status_and_missing_reason(self):
        p = self.approved()
        for kw in (dict(status="nonsense"), dict(status=CS.BOUNCED), dict(status=CS.RETURNED, note=" "),
                   dict(status=CS.RECEIVED, note="x")):
            with self.assertRaises(ValueError, msg=str(kw)):
                set_cheque_status(payment=p, actor=self.accountant, **kw)
        p.refresh_from_db()
        self.assertEqual(p.cheque_status, CS.RECEIVED)
        p = set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.accountant)
        with self.assertRaises(ValueError):
            set_cheque_status(payment=p, status=CS.RECEIVED, actor=self.accountant)    # بازگشت بدون دلیل
        self.assertEqual(set_cheque_status(payment=p, status=CS.RECEIVED, actor=self.accountant,
                                           note="از بانک پس آمد").cheque_status, CS.RECEIVED)

    def test_endorsed_name_is_optional_and_cleared_later(self):
        p = self.approved()
        p = set_cheque_status(payment=p, status=CS.ENDORSED, actor=self.accountant, endorsed_to="  آقای رضایی ")
        self.assertEqual(p.cheque_endorsed_to, "آقای رضایی")
        p = set_cheque_status(payment=p, status=CS.COLLECTED, actor=self.accountant)
        self.assertEqual(p.cheque_endorsed_to, "")
        q = self.approved(number="6543210987654321")
        q = set_cheque_status(payment=q, status=CS.ENDORSED, actor=self.accountant)
        self.assertEqual((q.cheque_status, q.cheque_endorsed_to), (CS.ENDORSED, ""))

    def test_only_reviewers_and_only_approved_cheques(self):
        p = self.approved()
        with self.assertRaises(ValueError):
            set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.tech)
        with self.assertRaises(ValueError):
            set_cheque_status(payment=self.pending(), status=CS.DEPOSITED, actor=self.accountant)
        card = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100,
                                      claimed_amount=100, status=Payment.Status.APPROVED)
        with self.assertRaises(ValueError):
            set_cheque_status(payment=card, status=CS.DEPOSITED, actor=self.accountant)

    def test_customer_sees_bounce_but_no_internal_status(self):
        p = self.approved()
        p = set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.accountant)
        self.assertEqual((p.status_label, p.status_variant), ("تاییدشده", "success"))
        p = set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت")
        self.assertEqual((p.status_label, p.status_variant), ("چک برگشت خورد", "error"))


class ChequeBounceMoneyTests(ChequeBase):
    def test_bounce_removes_the_money_everywhere_and_reopens_invoice(self):
        p = self.approved(amount=1000000)
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.status, self.invoice.paid_amount), (Invoice.Status.PAID, Decimal("1000000")))
        self.assertEqual(accounting.accounting_overview("all")["collected"], Decimal("1000000"))
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت خورد")
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.status, self.invoice.paid_amount), (Invoice.Status.SENT, Decimal("0")))
        self.assertIsNone(self.invoice.settled_at)
        self.assertEqual(accounting.accounting_overview("all")["collected"], Decimal("0"))
        self.assertFalse(counted_payments(Payment.objects.all()).exists())

    def test_partial_payment_keeps_other_money_and_returns_to_sent_when_none_left(self):
        card = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100000,
                                      claimed_amount=100000, reference_number="R")
        approve_payment(card, approved_by=self.accountant, verified_amount="100000")
        cheque = self.approved(amount=400000)
        self.assertEqual(self.paid(), Decimal("500000"))
        set_cheque_status(payment=cheque, status=CS.RETURNED, actor=self.accountant, note="پس داده شد")
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.status, self.invoice.paid_amount), (Invoice.Status.PARTIALLY_PAID, Decimal("100000")))

    def test_only_money_bouncing_sends_partially_paid_back_to_sent(self):
        p = self.approved(amount=400000)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.SENT)

    def test_bounced_cheque_does_not_block_cancelling_the_invoice(self):
        p = self.approved()
        with self.assertRaises(ValueError):
            cancel_invoice(invoice=self.invoice, reason="x", actor=self.manager)
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت")
        self.invoice.refresh_from_db()
        cancel_invoice(invoice=self.invoice, reason="x", actor=self.manager)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.CANCELLED)


class ChequeInfoTests(ChequeBase):
    def test_edit_info_logs_and_noop_or_stranger_is_refused(self):
        p = self.approved()
        new_due = self.future + timedelta(days=5)
        p = update_cheque_info(payment=p, number=CN, bank="ملت", due_date=new_due, actor=self.accountant)
        self.assertEqual((p.cheque_bank, p.cheque_due_date), ("ملت", new_due))
        with self.assertRaises(ValueError):
            update_cheque_info(payment=p, number=CN, bank="ملت", due_date=new_due, actor=self.accountant)
        with self.assertRaises(ValueError):
            update_cheque_info(payment=p, number=CN, bank="ملت", due_date=new_due + timedelta(days=1), actor=self.tech)
        last = ChequeEvent.objects.filter(payment=p).last()
        self.assertEqual(last.from_status, last.to_status)

    def test_accountant_cheque_needs_due_date_and_starts_received(self):
        kw = dict(invoice=self.invoice, method=Payment.Method.CHEQUE, amount_raw="100000", paid_date=None,
                  reference_number="", note="", cheque_number=CN, cheque_bank="ملی", actor=self.accountant)
        with self.assertRaises(ValueError):
            accounting.record_accountant_payment(receipt_file=make_image_file("c1.png"), **kw)
        p = accounting.record_accountant_payment(receipt_file=make_image_file("c2.png"),
                                                 cheque_due_date=self.future, **kw)
        self.assertEqual((p.status, p.cheque_status, p.cheque_due_date), (Payment.Status.APPROVED, CS.RECEIVED, self.future))
        self.assertTrue(ChequeEvent.objects.filter(payment=p).exists())


class CountedPaymentsGuardTests(TestCase):
    def test_money_sums_go_through_counted_payments(self):
        base = Path(settings.BASE_DIR)
        for rel in ("finance/accounting.py", "finance/reports.py", "finance/services.py"):
            self.assertIn("counted_payments(", (base / rel).read_text(encoding="utf-8"), rel)
        for rel in ("finance/accounting.py", "finance/reports.py"):
            self.assertNotIn("exclude(method=Payment.Method.CREDIT)", (base / rel).read_text(encoding="utf-8"), rel)
        self.assertEqual((base / "finance/services.py").read_text(encoding="utf-8")
                         .count("exclude(method=Payment.Method.CREDIT)"), 1)
