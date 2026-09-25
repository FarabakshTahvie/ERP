from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, OTPCode


class PasswordResetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="active_user", phone_number="09121111111",
            password="StrongPassword123", is_active=True,
        )

    @mock.patch("utils.sms.SMSService.send_otp")
    def test_unknown_phone_shows_not_found_message_and_no_sms(self, mock_sms):
        client = Client()
        resp = client.post(reverse("accounts:password_reset_request"), {"phone_number": "09129999999"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("حساب کاربری فعالی با این شماره‌ی موبایل پیدا نشد", resp.content.decode("utf-8"))
        mock_sms.assert_not_called()

    @mock.patch("utils.sms.SMSService.send_otp")
    def test_existing_phone_renders_verify_form(self, mock_sms):
        mock_sms.return_value = {"success": True, "message_id": "123"}
        client = Client()
        resp = client.post(reverse("accounts:password_reset_request"), {"phone_number": "09121111111"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("کد تایید پیامک‌شده", resp.content.decode("utf-8"))
        self.assertIn("کد تایید برای این شماره پیامک شد.", resp.content.decode("utf-8"))
        mock_sms.assert_called_once()
