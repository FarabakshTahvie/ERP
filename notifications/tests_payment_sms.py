from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from core.models import Party
from decimal import Decimal
from django.utils import timezone
from finance.models import Invoice, Payment
from finance.services import approve_payment, cancel_invoice, reject_payment
from notifications.models import Notification, NotificationType as NT
from notifications.services import resend_notification
from projects.models import Project
from utils.sms import SMSService
from utils.test_helpers import make_accountant

OK = {"success": True, "message_id": 1}
CONF = "notifications.services.SMSService.send_payment_confirmed"
REJ = "notifications.services.SMSService.send_payment_rejected"


class PaymentSmsBase(TestCase):
    def setUp(self):
        call_command("setup_notification_policies", stdout=StringIO())
        self.manager = User.objects.create_user(username="ps_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("ps_acc")
        self.party = Party.objects.create(name="مشتری پیامک پرداخت", is_client=True, phone_number="09125550123")
        self.customer = User.objects.create_user(username="ps_cli", password="pw", role=User.Role.CLIENT, party=self.party,
                                                 phone_number="09125550123", first_name="علی")
        self.project = Project.objects.create(name="پروژه پیامک پرداخت", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-PS-1", billed_party=self.party,
                                              total_amount=Decimal("1000000"), issue_date=timezone.localdate(),
                                              status=Invoice.Status.SENT)

    def pending(self, method=Payment.Method.CARD_TO_CARD, amount=400000):
        credit = method == Payment.Method.CREDIT
        return Payment.objects.create(invoice=self.invoice, method=method, amount=amount, claimed_amount=amount,
                                      reference_number="" if credit else "R", note="شرایط تسویه" if credit else "")

    def approve(self, p, amount="400000"):
        with self.captureOnCommitCallbacks(execute=True):
            return approve_payment(p, approved_by=self.accountant, verified_amount=amount)


class ConfirmedSmsTests(PaymentSmsBase):
    def test_nothing_is_sent_before_commit(self):
        with mock.patch(CONF, return_value=OK) as m:
            approve_payment(self.pending(), approved_by=self.accountant, verified_amount="400000")
        m.assert_not_called()
        self.assertEqual(Notification.objects.count(), 0)

    def test_failed_sms_does_not_block_approval_and_can_be_resent(self):
        with mock.patch(CONF, return_value={"success": False, "error": "e", "http_status": 400}):
            p = self.approve(self.pending())
        self.assertEqual(p.status, Payment.Status.APPROVED)
        n = Notification.objects.get()
        self.assertEqual(n.status, Notification.Status.FAILED)
        with mock.patch(CONF, return_value=OK):
            n = resend_notification(n, actor=self.manager)
        self.assertEqual(n.status, Notification.Status.SMS_SENT)


class RejectedSmsTests(PaymentSmsBase):
    def test_reject_sends_the_rejection_template(self):
        with mock.patch(REJ, return_value=OK) as m:
            with self.captureOnCommitCallbacks(execute=True):
                reject_payment(self.pending(), rejected_by=self.accountant, reason="رسید خوانا نیست")
        m.assert_called_once()
        kw = m.call_args.kwargs
        self.assertEqual(kw["number"], "INV-PS-1")
        self.assertNotIn("name", kw)
        self.assertTrue(kw["link"].startswith("s/"))
        self.assertNotIn("remaining", kw)
        self.assertEqual(Notification.objects.get().notification_type, NT.PAYMENT_REJECTED)

    def test_cancelling_the_invoice_rejects_pending_payments_silently(self):
        p = self.pending()
        with mock.patch(REJ, return_value=OK) as m:
            with self.captureOnCommitCallbacks(execute=True):
                cancel_invoice(invoice=self.invoice, reason="لغو", actor=self.manager)
        m.assert_not_called()
        p.refresh_from_db()
        self.assertEqual(p.status, Payment.Status.REJECTED)
        self.assertEqual(Notification.objects.count(), 0)


class TemplateRegistryTests(PaymentSmsBase):
    def test_payment_templates_have_matching_parameter_names(self):
        for result in (SMSService().send_payment_confirmed("0912", "N", "5", "s/abc"),
                       SMSService().send_payment_rejected("0912", "N", "s/abc")):
            self.assertEqual(result["error"], "SMS_IR_API_KEY is empty")
