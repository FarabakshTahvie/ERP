from datetime import timedelta
from decimal import Decimal
from unittest import mock

import requests
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance import gateway
from finance.models import GatewayTransaction, Invoice, Payment
from projects.models import (
    Project, ProjectStage, StageApproval, WorkflowStepTemplate, WorkflowTemplate,
)
from utils.test_helpers import make_accountant

AUTHORITY = "A0000000000000000000000000000wwOGYpd"
REQUEST_OK = {"data": {"code": 100, "message": "Success", "authority": AUTHORITY,
                       "fee_type": "Merchant", "fee": 100}, "errors": []}
VERIFY_OK = {"data": {"code": 100, "message": "Verified", "card_pan": "502229******5995",
                      "ref_id": 201, "fee_type": "Merchant", "fee": 0}, "errors": []}
VERIFY_ALREADY = {"data": {"code": 101, "message": "Verified", "card_pan": "502229******5995",
                           "ref_id": 202}, "errors": []}
REFUSED = {"data": [], "errors": {"code": -51, "message": "x", "validations": []}}
POST = "finance.gateway.requests.post"


def reply(payload):
    response = mock.Mock()
    response.json.return_value = payload
    return response


@override_settings(ZARINPAL_ENABLED=True, ZARINPAL_MERCHANT_ID="m" * 36, ZARINPAL_SANDBOX=False,
                   SITE_BASE_URL="https://example.test")
class GatewayBase(TestCase):
    def setUp(self):
        self.party = Party.objects.create(name="مشتری درگاه", is_client=True, phone_number="09140000001")
        self.user = User.objects.create_user(username="gw_client", password="pw", role=User.Role.CLIENT,
                                             party=self.party, phone_number="09140000001")
        self.project = Project.objects.create(name="پروژه درگاه", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-GW-1", billed_party=self.party,
                                              total_amount=Decimal("5000000"), issue_date=timezone.localdate())
        self.client = Client()
        self.client.force_login(self.user)

    def pending_tx(self, amount="2000000"):
        return GatewayTransaction.objects.create(invoice=self.invoice, user=self.user,
                                                 amount=Decimal(amount), authority=AUTHORITY)

    def callback(self, status="OK", authority=AUTHORITY):
        return Client().get(reverse("finance:gateway_callback"), {"Authority": authority, "Status": status})

    def start(self, client=None, **data):
        return (client or self.client).post(reverse("finance:gateway_start", args=[self.invoice.uuid]), data)


class GatewaySafetyTests(GatewayBase):
    def test_sandbox_is_refused_when_debug_is_off(self):
        with self.settings(ZARINPAL_SANDBOX=True, DEBUG=False):
            self.assertFalse(gateway.gateway_enabled())
        with self.settings(ZARINPAL_SANDBOX=True, DEBUG=True):
            self.assertTrue(gateway.gateway_enabled())

    def test_disabled_gateway_cannot_start(self):
        with self.settings(ZARINPAL_ENABLED=False), mock.patch(POST) as post:
            self.start(amount="1000000")
        post.assert_not_called()
        self.assertFalse(GatewayTransaction.objects.exists())


class GatewayStartTests(GatewayBase):
    def test_start_sends_rial_amount_manual_verify_and_redirects(self):
        with mock.patch(POST, return_value=reply(REQUEST_OK)) as post:
            r = self.start(amount="2,000,000")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["amount"], 20000000)
        self.assertIs(payload["metadata"]["auto_verify"], False)
        self.assertEqual(payload["callback_url"], "https://example.test" + reverse("finance:gateway_callback"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].endswith("/pg/StartPay/" + AUTHORITY))
        tx = GatewayTransaction.objects.get()
        self.assertEqual((tx.status, tx.amount, tx.authority), ("pending", Decimal("2000000"), AUTHORITY))
        self.assertFalse(Payment.objects.exists())   # تا verify نشود پرداختی در فاکتور نیست

    def test_empty_amount_means_whole_remaining(self):
        with mock.patch(POST, return_value=reply(REQUEST_OK)) as post:
            self.start(amount="")
        self.assertEqual(post.call_args.kwargs["json"]["amount"], 50000000)

    def test_amount_above_remaining_or_below_minimum_is_refused(self):
        with mock.patch(POST) as post:
            self.start(amount="5,000,001")
            self.start(amount="500")
        post.assert_not_called()
        self.assertFalse(GatewayTransaction.objects.exists())

    def test_only_the_invoice_owner_can_start(self):
        outsider = User.objects.create_user(username="gw_out", password="pw", role=User.Role.CLIENT)
        accountant = make_accountant("gw_acc")
        with mock.patch(POST) as post:
            for user in (outsider, accountant):
                other = Client()
                other.force_login(user)
                self.assertEqual(self.start(client=other, amount="1000000").status_code, 404)
        post.assert_not_called()

    def test_expired_proforma_cannot_start(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(valid_until=timezone.localdate() - timedelta(days=1))
        with mock.patch(POST) as post:
            r = self.start(amount="1000000")
        post.assert_not_called()
        self.assertNotIn("zarinpal", r["Location"])
        self.assertFalse(GatewayTransaction.objects.exists())

    def test_gateway_rejection_creates_no_transaction(self):
        rejected = reply({"data": [], "errors": {"code": -10, "message": "x", "validations": []}})
        with mock.patch(POST, return_value=rejected):
            r = self.start(amount="1000000")
        self.assertNotIn("zarinpal", r["Location"])
        self.assertFalse(GatewayTransaction.objects.exists())


class GatewayCallbackTests(GatewayBase):
    def test_success_records_one_approved_payment_using_stored_amount(self):
        tx = self.pending_tx("2000000")
        with mock.patch(POST, return_value=reply(VERIFY_OK)) as post:
            first = self.callback()
            second = self.callback()
        self.assertEqual(post.call_count, 1)   # تکرار برگشت دوباره verify یا ثبت نمی‌کند
        payload = post.call_args.kwargs["json"]
        self.assertEqual((payload["amount"], payload["authority"]), (20000000, AUTHORITY))
        payment = Payment.objects.get()
        self.assertEqual((payment.method, payment.status, payment.amount, payment.reference_number),
                         ("gateway", "approved", Decimal("2000000"), "201"))
        self.invoice.refresh_from_db()
        self.assertEqual((self.invoice.paid_amount, self.invoice.status), (Decimal("2000000"), "partially_paid"))
        tx.refresh_from_db()
        self.assertEqual((tx.status, tx.payment_id, tx.ref_id), ("paid", payment.pk, "201"))
        self.assertEqual((first.status_code, second.status_code), (302, 302))

    def test_already_verified_code_101_is_recorded_once(self):
        self.pending_tx()
        with mock.patch(POST, return_value=reply(VERIFY_ALREADY)):
            self.callback()
            self.callback()
        self.assertEqual(Payment.objects.count(), 1)

    def test_cancelled_status_never_verifies_or_records(self):
        tx = self.pending_tx()
        with mock.patch(POST) as post:
            self.callback(status="NOK")
        post.assert_not_called()
        tx.refresh_from_db()
        self.assertEqual(tx.status, "pending")
        self.assertFalse(Payment.objects.exists())

    def test_unknown_authority_is_404(self):
        with mock.patch(POST) as post:
            self.assertEqual(self.callback(authority="Aunknown").status_code, 404)
        post.assert_not_called()

    def test_cancelled_invoice_is_not_verified_so_gateway_refunds(self):
        tx = self.pending_tx()
        Invoice.objects.filter(pk=self.invoice.pk).update(status=Invoice.Status.CANCELLED)
        with mock.patch(POST) as post:
            self.callback()
        post.assert_not_called()
        tx.refresh_from_db()
        self.assertEqual(tx.status, "failed")
        self.assertFalse(Payment.objects.exists())

    def test_amount_above_remaining_is_not_verified(self):
        tx = self.pending_tx("3000000")
        Payment.objects.create(invoice=self.invoice, method=Payment.Method.GATEWAY, amount=Decimal("3000000"),
                               status=Payment.Status.APPROVED)   # مانده می‌شود ۲ میلیون
        with mock.patch(POST) as post:
            self.callback()
        post.assert_not_called()
        tx.refresh_from_db()
        self.assertEqual(tx.status, "failed")
        self.assertEqual(Payment.objects.count(), 1)

    def test_gateway_refusal_marks_failed_without_payment(self):
        tx = self.pending_tx()
        with mock.patch(POST, return_value=reply(REFUSED)):
            self.callback()
        tx.refresh_from_db()
        self.assertEqual((tx.status, tx.result_code), ("failed", -51))
        self.assertFalse(Payment.objects.exists())

    def test_network_error_keeps_pending_and_a_retry_succeeds(self):
        tx = self.pending_tx()
        with mock.patch(POST, side_effect=requests.exceptions.ConnectionError()):
            self.callback()
        tx.refresh_from_db()
        self.assertEqual(tx.status, "pending")
        self.assertFalse(Payment.objects.exists())
        with mock.patch(POST, return_value=reply(VERIFY_OK)):
            self.callback()
        self.assertEqual(Payment.objects.count(), 1)


class GatewayApprovalTests(GatewayBase):
    def setUp(self):
        super().setUp()
        template = WorkflowTemplate.objects.create(name="قالب درگاه")
        step = WorkflowStepTemplate.objects.create(template=template, order=1, title="تایید",
                                                   requires_payment_selection=True)
        self.stage = ProjectStage.objects.create(project=self.project, step_template=step, order=1, title="تایید",
                                                 status=ProjectStage.Status.WAITING_APPROVAL)
        self.approval = StageApproval.objects.create(stage=self.stage, sent_to_party=self.party)
        self.pending_tx()

    def test_online_payment_also_approves_the_waiting_stage(self):
        with mock.patch(POST, return_value=reply(VERIFY_OK)):
            self.callback()
        self.approval.refresh_from_db()
        self.stage.refresh_from_db()
        self.assertEqual(self.approval.decision, StageApproval.Decision.APPROVED)
        self.assertEqual(self.stage.status, ProjectStage.Status.DONE)

    def test_failed_approval_never_loses_the_verified_payment(self):
        with mock.patch(POST, return_value=reply(VERIFY_OK)), \
                mock.patch("projects.services.decide_stage_approval", side_effect=RuntimeError("boom")):
            self.callback()
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(GatewayTransaction.objects.get().status, "paid")
