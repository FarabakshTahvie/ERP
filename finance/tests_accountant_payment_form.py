import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance.models import AccountingEvent, ChequeEvent, Invoice, Payment
from projects.models import Project
from utils.jalali import jalali_str
from utils.test_helpers import make_accountant, make_image_file

CN = "1234567890123456"


def jd(d):
    return jalali_str(d, fmt="%Y/%m/%d", persian=False)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AccountantFormBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.manager = User.objects.create_user(username="af_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("af_acc")
        self.tech = User.objects.create_user(username="af_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری فرم پرداخت", is_client=True, phone_number="09127773001")
        self.project = Project.objects.create(name="پروژه فرم پرداخت", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-AF-1", billed_party=self.party,
                                              total_amount=Decimal("1000000"), issue_date=timezone.localdate(),
                                              status=Invoice.Status.SENT)
        self.url = reverse("finance:accounting_add_payment", args=[self.project.id])
        self.page = reverse("finance:accounting_project", args=[self.project.id])
        self.future = timezone.localdate() + timedelta(days=30)

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def post(self, **data):
        return self.login(self.accountant).post(self.url, data, follow=True)


class FormVisibilityTests(AccountantFormBase):
    def test_reviewers_see_the_form_while_there_is_a_balance(self):
        for user in (self.accountant, self.manager):
            self.assertContains(self.login(user).get(self.page), self.url, msg_prefix=user.username)

    def test_no_form_for_cancelled_or_fully_paid_invoice(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(paid_amount=self.invoice.total_amount)
        self.assertNotContains(self.login(self.accountant).get(self.page), self.url)
        Invoice.objects.filter(pk=self.invoice.pk).update(paid_amount=0, status=Invoice.Status.CANCELLED)
        self.assertNotContains(self.login(self.accountant).get(self.page), self.url)

    def test_technician_gets_neither_page_nor_post(self):
        c = self.login(self.tech)
        self.assertIn("login", c.get(self.page).url)
        resp = c.post(self.url, {"method": "cash", "amount": "1000", "note": "x"})
        self.assertIn("login", resp.url)
        self.assertFalse(Payment.objects.exists())


class FormPostTests(AccountantFormBase):
    def test_cash_payment_is_approved_at_once_and_logged(self):
        self.post(method="cash", amount="300000", note="حضوری آمد")
        p = Payment.objects.get()
        self.assertEqual((p.method, p.status, p.amount, p.approved_by), ("cash", Payment.Status.APPROVED,
                                                                         Decimal("300000"), self.accountant))
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.paid_amount, self.invoice.status),
                         (Decimal("300000"), Invoice.Status.PARTIALLY_PAID))
        self.assertTrue(AccountingEvent.objects.filter(project=self.project, kind="payment").exists())

    def test_cash_needs_a_note_and_amount_is_capped_by_the_balance(self):
        resp = self.post(method="cash", amount="1000", note="")
        self.assertContains(resp, "توضیح بنویسید")
        resp = self.post(method="cash", amount="2000000", note="زیاد")
        self.assertContains(resp, "بیشتر است")
        self.assertFalse(Payment.objects.exists())

    def test_future_paid_date_is_refused(self):
        resp = self.post(method="cash", amount="1000", note="x", paid_date=jd(timezone.localdate() + timedelta(days=3)))
        self.assertContains(resp, "آینده")
        self.assertFalse(Payment.objects.exists())

    def test_cheque_needs_due_date_and_starts_as_received(self):
        self.post(method="cheque", amount="400000", cheque_number=CN, cheque_bank="ملی",
                  receipt_file=make_image_file("c1.png"))
        self.assertFalse(Payment.objects.exists())
        self.post(method="cheque", amount="400000", cheque_number=CN, cheque_bank="ملی",
                  cheque_due_date=jd(self.future), receipt_file=make_image_file("c2.png"))
        p = Payment.objects.get()
        self.assertEqual((p.status, p.cheque_status, p.cheque_due_date), (Payment.Status.APPROVED, "received", self.future))
        self.assertTrue(ChequeEvent.objects.filter(payment=p).exists())

    def test_past_due_cheque_saves_with_a_warning(self):
        old = timezone.localdate() - timedelta(days=10)
        resp = self.post(method="cheque", amount="400000", cheque_number=CN, cheque_bank="ملی",
                         cheque_due_date=jd(old), receipt_file=make_image_file("c3.png"))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertContains(resp, "تاریخ سررسید این چک گذشته است")
