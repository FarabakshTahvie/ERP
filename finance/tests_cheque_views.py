from datetime import timedelta
from decimal import Decimal
 
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
 
from accounts.models import User
from core.models import Party
from finance.models import ChequeEvent, Invoice, Payment
from finance.services import approve_payment, set_cheque_status
from projects.models import Project
from utils.jalali import jalali_str
from utils.test_helpers import make_accountant
 
CN = "1234567890123456"
CS = Payment.ChequeStatus
 
 
def jd(d):
    return jalali_str(d, fmt="%Y/%m/%d", persian=False)
 
 
class ChequeViewBase(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="cv_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("cv_acc")
        self.tech = User.objects.create_user(username="cv_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری نمای چک", is_client=True, phone_number="09127772001")
        self.customer = User.objects.create_user(username="cv_cli", password="pw", role=User.Role.CLIENT, party=self.party)
        self.project = Project.objects.create(name="پروژه نمای چک", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-CV-1", billed_party=self.party,
                                              total_amount=Decimal("1000000"), issue_date=timezone.localdate(),
                                              status=Invoice.Status.SENT)
        self.future = timezone.localdate() + timedelta(days=30)
 
    def login(self, user):
        c = Client()
        c.force_login(user)
        return c
 
    def pending(self, amount=400000, **kw):
        return Payment.objects.create(invoice=self.invoice, method=Payment.Method.CHEQUE, amount=amount,
                                      claimed_amount=amount, **kw)
 
    def approved(self, amount=400000, number=CN):
        return approve_payment(self.pending(amount), approved_by=self.accountant, verified_amount=str(amount),
                               cheque_number=number, cheque_bank="ملی", cheque_due_date=self.future)
 
    def detail(self, p):
        return reverse("finance:payment_detail", args=[p.id])
 
    def decide(self, p, **data):
        data.setdefault("action", "approve")
        data.setdefault("verified_amount", "400000")
        return self.login(self.accountant).post(reverse("finance:payment_decide", args=[p.id]), data, follow=True)
 
 
class ChequeApproveViewTests(ChequeViewBase):
    def test_approval_needs_sayyadi_and_due_date_in_the_form(self):
        p = self.pending()
        for data in (dict(cheque_number="123", cheque_due_date=jd(self.future)),
                     dict(cheque_number=CN, cheque_due_date="")):
            self.decide(p, cheque_bank="ملی", **data)
            p.refresh_from_db()
            self.assertEqual(p.status, Payment.Status.PENDING, str(data))
        self.decide(p, cheque_number="۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶", cheque_bank="ملی", cheque_due_date=jd(self.future))
        p.refresh_from_db()
        self.assertEqual((p.status, p.cheque_status, p.cheque_number, p.cheque_due_date),
                         (Payment.Status.APPROVED, CS.RECEIVED, CN, self.future))
 

class ChequeStatusViewTests(ChequeViewBase):

 
    def test_only_reviewers_can_post(self):
        p = self.approved()
        for user in (self.tech, self.customer):
            resp = self.login(user).post(reverse("finance:payment_cheque_status", args=[p.id]), {"status": "deposited"})
            self.assertIn("login", resp.url, user.username)
            resp = self.login(user).post(reverse("finance:payment_cheque_info", args=[p.id]),
                                         {"number": CN, "bank": "x", "due_date": jd(self.future)})
            self.assertIn("login", resp.url, user.username)
        p.refresh_from_db()
        self.assertEqual((p.cheque_status, p.cheque_bank), (CS.RECEIVED, "ملی"))
 

 
    def test_customer_never_sees_the_internal_status(self):
        p = self.approved()
        set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.accountant)
        url = reverse("finance:portal_invoice_detail", args=[self.invoice.uuid])
        c = self.login(self.customer)
        self.assertNotContains(c.get(url), "واگذار به بانک")
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت")
        self.assertContains(c.get(url), "چک برگشت خورد")
