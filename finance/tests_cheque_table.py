import itertools
from datetime import timedelta
from decimal import Decimal
 
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
 
from accounts.models import User
from core.models import Party
from finance import accounting
from finance.models import Invoice, Payment
from finance.services import approve_payment, set_cheque_status
from projects.models import Project
from utils.jalali import to_fa_digits
from utils.test_helpers import make_accountant
from utils.utils import separate_digits
 
CS = Payment.ChequeStatus
 
 
def fa(n):
    return to_fa_digits(separate_digits(n))
 
 
class ChequeTableBase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="ct_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("ct_acc")
        self.party = Party.objects.create(name="مشتری جدول چک", is_client=True, phone_number="09127774001")
        self.project = Project.objects.create(name="پروژه جدول چک", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-CT-1", billed_party=self.party,
                                              total_amount=Decimal("10000000"), issue_date=timezone.localdate(),
                                              status=Invoice.Status.SENT)
        self.today = timezone.localdate()
        self.seq = itertools.count(1)
 
    def login(self, user):
        c = Client()
        c.force_login(user)
        return c
 
    def cheque(self, days, amount, status=None):
        p = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CHEQUE, amount=amount, claimed_amount=amount)
        p = approve_payment(p, approved_by=self.accountant, verified_amount=str(amount),
                            cheque_number=f"{next(self.seq):016d}", cheque_bank="ملی",
                            cheque_due_date=self.today + timedelta(days=days))
        if status:
            set_cheque_status(payment=p, status=status, actor=self.accountant, note="x")
        return p
 
    def rows(self, **params):
        resp = self.login(self.accountant).get(reverse("finance:payments_table"), params)
        return [r["cells"][3]["value"] for r in resp.context["rows"]]
 
    def seed(self):
        """A:+3  B:+7  C:+8  D:-5  E:+2 واگذار به بانک  F:+1 وصول‌شده + کارت به کارت + چک منتظر تایید"""
        self.a = self.cheque(3, 100001)
        self.b = self.cheque(7, 100002)
        self.c = self.cheque(8, 100003)
        self.d = self.cheque(-5, 100004)
        self.e = self.cheque(2, 100005, CS.DEPOSITED)
        self.f = self.cheque(1, 100006, CS.COLLECTED)
        card = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100007,
                                      claimed_amount=100007, reference_number="R")
        approve_payment(card, approved_by=self.accountant, verified_amount="100007")
        Payment.objects.create(invoice=self.invoice, method=Payment.Method.CHEQUE, amount=100008, claimed_amount=100008,
                               cheque_due_date=self.today + timedelta(days=1))
 
 
class ChequeSoonTableTests(ChequeTableBase):
    def test_soon_filter_keeps_only_open_cheques_due_within_seven_days_or_overdue(self):
        self.seed()
        got = self.rows(py_f_cheque_soon="1", py_sort="cheque_due_date", py_dir="asc")
        self.assertEqual(got, [fa(100004), fa(100005), fa(100001), fa(100002)])   # D, E, A, B
 
    def test_sort_direction_desc_is_reversed(self):
        self.seed()
        got = self.rows(py_f_cheque_soon="1", py_sort="cheque_due_date", py_dir="desc")
        self.assertEqual(got, [fa(100002), fa(100001), fa(100005), fa(100004)])
 
