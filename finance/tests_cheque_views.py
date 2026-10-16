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
 
    def test_past_due_date_approves_with_a_warning(self):
        p = self.pending()
        old = timezone.localdate() - timedelta(days=20)
        resp = self.decide(p, cheque_number=CN, cheque_bank="ملی", cheque_due_date=jd(old))
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.Status.APPROVED)
        self.assertContains(resp, "تاریخ سررسید این چک گذشته است")
 
    def test_absent_cheque_fields_keep_what_the_customer_registered(self):
        p = self.pending(cheque_number=CN, cheque_due_date=self.future)
        self.decide(p)
        p.refresh_from_db()
        self.assertEqual((p.status, p.cheque_number), (Payment.Status.APPROVED, CN))
 
    def test_pending_page_shows_the_fields_but_no_status_card(self):
        p = self.pending()
        resp = self.login(self.accountant).get(self.detail(p))
        self.assertContains(resp, 'name="cheque_due_date"')
        self.assertNotContains(resp, "وضعیت چک (داخلی)")
 
 
class ChequeStatusViewTests(ChequeViewBase):
    def test_card_is_shown_to_reviewers_for_approved_cheques_only(self):
        p = self.approved()
        for user in (self.accountant, self.manager):
            resp = self.login(user).get(self.detail(p))
            self.assertContains(resp, "وضعیت چک (داخلی)", msg_prefix=user.username)
            self.assertContains(resp, "تحویل گرفته‌شده")
        card = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100,
                                      claimed_amount=100, status=Payment.Status.APPROVED, reference_number="R")
        self.assertNotContains(self.login(self.accountant).get(self.detail(card)), "وضعیت چک (داخلی)")
 
    def test_status_change_is_saved_with_history(self):
        p = self.approved()
        c = self.login(self.accountant)
        c.post(reverse("finance:payment_cheque_status", args=[p.id]), {"status": "deposited"})
        p.refresh_from_db()
        self.assertEqual(p.cheque_status, CS.DEPOSITED)
        self.assertEqual(ChequeEvent.objects.filter(payment=p).count(), 2)
        self.assertContains(c.get(self.detail(p)), "واگذار به بانک")
 
    def test_endorsed_name_is_saved_and_reason_statuses_need_a_reason(self):
        p = self.approved()
        c = self.login(self.accountant)
        url = reverse("finance:payment_cheque_status", args=[p.id])
        c.post(url, {"status": "bounced", "note": ""})
        p.refresh_from_db()
        self.assertEqual(p.cheque_status, CS.RECEIVED)
        c.post(url, {"status": "endorsed", "endorsed_to": " آقای رضایی "})
        p.refresh_from_db()
        self.assertEqual((p.cheque_status, p.cheque_endorsed_to), (CS.ENDORSED, "آقای رضایی"))
 
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
 
    def test_info_edit_saves_and_a_noop_is_refused(self):
        p = self.approved()
        c = self.login(self.accountant)
        url = reverse("finance:payment_cheque_info", args=[p.id])
        new_due = self.future + timedelta(days=5)
        c.post(url, {"number": CN, "bank": "ملت", "due_date": jd(new_due)})
        p.refresh_from_db()
        self.assertEqual((p.cheque_bank, p.cheque_due_date), ("ملت", new_due))
        resp = c.post(url, {"number": CN, "bank": "ملت", "due_date": jd(new_due)}, follow=True)
        self.assertContains(resp, "تغییری ثبت نشد")
 
    def test_customer_never_sees_the_internal_status(self):
        p = self.approved()
        set_cheque_status(payment=p, status=CS.DEPOSITED, actor=self.accountant)
        url = reverse("finance:portal_invoice_detail", args=[self.invoice.uuid])
        c = self.login(self.customer)
        self.assertNotContains(c.get(url), "واگذار به بانک")
        set_cheque_status(payment=p, status=CS.BOUNCED, actor=self.accountant, note="برگشت")
        self.assertContains(c.get(url), "چک برگشت خورد")
