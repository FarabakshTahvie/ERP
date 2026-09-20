import uuid
import os
import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from utils.push_notification import NajvaService
from utils.sms import SMSService
from utils.models import PushDevice, DeviceType
from notifications.models import Notification, NotificationPolicy, ChannelPolicy, NotificationType, NotificationClickEvent
from notifications.services import create_notification, dispatch_notification

User = get_user_model()


class NajvaServiceTest(TestCase):
    @patch("utils.push_notification.requests.post")
    def test_najva_send_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Entries": {
                "request_id": "req-123",
                "tokens": [{"token": "token-1", "status": "Sent"}]
            }
        }
        mock_post.return_value = mock_resp

        service = NajvaService()
        service.api_key = "test_api_key"
        service.website_id = "test_web_id"

        res = service.send(title="تست", body="متن", subscriber_tokens=["token-1"])
        self.assertTrue(res["success"])
        self.assertEqual(res["invalid_tokens"], [])

    @patch("utils.push_notification.requests.post")
    def test_najva_invalid_tokens(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "Entries": {
                "tokens": [
                    {"token": "bad-token", "status": "InvalidToken"},
                    {"token": "good-token", "status": "Sent"}
                ]
            }
        }
        mock_post.return_value = mock_resp

        service = NajvaService()
        service.api_key = "test_key"
        service.website_id = "test_web"

        res = service.send(title="تست", body="متن", subscriber_tokens=["bad-token", "good-token"])
        self.assertTrue(res["success"])
        self.assertIn("bad-token", res["invalid_tokens"])

    @patch("utils.push_notification.requests.post")
    def test_najva_error_416(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 416
        mock_resp.text = "IP not whitelisted"
        mock_post.return_value = mock_resp

        service = NajvaService()
        service.api_key = "test_key"
        service.website_id = "test_web"

        res = service.send(title="تست", body="متن", subscriber_tokens=["token-1"])
        self.assertFalse(res["success"])
        self.assertIn("IP", res["error"])

    def test_najva_unconfigured(self):
        service = NajvaService()
        service.api_key = ""
        res = service.send(title="تست", body="متن", subscriber_tokens=["token-1"])
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "najva not configured")


class SMSServiceTest(TestCase):
    @patch("utils.sms.requests.post")
    def test_sms_send_pattern_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 1, "message": "موفق"}
        mock_post.return_value = mock_resp

        sms = SMSService()
        sms.api_key = "test_key"
        res = sms.send_otp("09120000000", "12345")
        self.assertTrue(res["success"])

        # بررسی payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["mobile"], "09120000000")
        self.assertEqual(kwargs["headers"]["X-API-KEY"], "test_key")

    def test_sms_missing_params(self):
        sms = SMSService()
        sms.api_key = "test_key"
        with self.assertRaises(ValueError):
            sms.send_pattern("09120000000", "login_otp")  # بدون code

    def test_sms_empty_key(self):
        sms = SMSService()
        sms.api_key = ""
        res = sms.send_otp("09120000000", "12345")
        self.assertFalse(res["success"])


class TrackingAndShortLinkTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", phone_number="09120000001", password="password")
        self.notification = Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.MANUAL,
            title="تست لینک",
            body="متن",
            real_target_url="/portal/invoices/123/",
        )

    def test_short_code_generated(self):
        self.assertIsNotNone(self.notification.short_code)
        self.assertEqual(len(self.notification.short_code), 7)
        self.assertTrue(self.notification.short_path.startswith("s/"))

    def test_click_tracking_normal_user(self):
        client = Client()
        url = f"/{self.notification.short_path}"
        resp = client.get(url, HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/portal/invoices/123/")

        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.seen_at)
        self.assertEqual(self.notification.status, Notification.Status.SEEN)
        self.assertEqual(NotificationClickEvent.objects.filter(notification=self.notification).count(), 1)

    def test_click_tracking_bot_ignored(self):
        client = Client()
        url = f"/{self.notification.short_path}"
        resp = client.get(url, HTTP_USER_AGENT="facebookexternalhit/1.1")
        self.assertEqual(resp.status_code, 302)

        self.notification.refresh_from_db()
        self.assertIsNone(self.notification.seen_at)
        self.assertEqual(NotificationClickEvent.objects.filter(notification=self.notification).count(), 0)

    def test_external_redirect_prevented(self):
        self.notification.real_target_url = "https://evil.com/phishing"
        self.notification.save()

        client = Client()
        url = f"/{self.notification.short_path}"
        resp = client.get(url, HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(resp.url, "/")


class DispatchAndNotificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser2", phone_number="09120000002", password="password")

    @patch("notifications.services.send_sms_channel")
    @patch("notifications.services.send_push_channel")
    def test_fallback_triggers_sms_when_no_push_device(self, mock_push, mock_sms):
        mock_push.return_value = False
        mock_sms.return_value = True

        policy, _ = NotificationPolicy.objects.get_or_create(
            notification_type=NotificationType.STAGE_APPROVAL_REQUEST,
            defaults={"channel_policy": ChannelPolicy.PUSH_THEN_SMS_FALLBACK}
        )

        create_notification(
            notification_type=NotificationType.STAGE_APPROVAL_REQUEST,
            user=self.user,
            title="تایید مرحله",
            body="متن",
        )

        mock_push.assert_called_once()
        mock_sms.assert_called_once()

    @patch("notifications.services.SMSService.send_invoice_issued")
    def test_password_cleared_after_sms(self, mock_sms_issued):
        mock_sms_issued.return_value = {"success": True}

        notif = create_notification(
            notification_type=NotificationType.INVOICE_ISSUED,
            user=self.user,
            title="فاکتور جدید",
            body="متن",
            extra_data={"invoice_number": "INV-1", "username": "testuser2", "password": "SecretPassword123"}
        )

        notif.refresh_from_db()
        self.assertEqual(notif.extra_data.get("password"), "")


class PushDeviceRegisterTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pushuser", password="password123")
        self.valid_uuid = str(uuid.uuid4())

    def test_unauthenticated_401(self):
        client = Client()
        resp = client.post(reverse("utils:register_push_device"), data={"token": self.valid_uuid}, content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_invalid_uuid_400(self):
        client = Client()
        client.force_login(self.user)
        resp = client.post(reverse("utils:register_push_device"), data={"token": "invalid-token"}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_valid_token_registered(self):
        client = Client()
        client.force_login(self.user)
        resp = client.post(reverse("utils:register_push_device"), data={"token": self.valid_uuid}, content_type="application/json")
        self.assertEqual(resp.status_code, 200)

        device = PushDevice.objects.get(registration_id=self.valid_uuid)
        self.assertEqual(device.user, self.user)


@unittest.skipUnless(os.environ.get("SMS_IR_SANDBOX_API_KEY"), "sandbox key not set")
class SMSSandboxIntegrationTest(TestCase):
    @override_settings(SMS_IR_API_KEY=os.environ.get("SMS_IR_SANDBOX_API_KEY", ""))
    def test_sandbox_otp(self):
        mobile = os.environ.get("SMS_TEST_MOBILE", "09120000000")
        result = SMSService().send_otp(mobile=mobile, code="12345")
        self.assertTrue(result["success"], result)
