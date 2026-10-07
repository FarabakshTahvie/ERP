import logging
from unittest import mock
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.cache import cache

from accounts.models import OTPCode, User
from accounts.celery_tasks import send_otp_sms_task


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OTPCeleryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="u1", phone_number="09151112233", password="pw")

    @mock.patch("accounts.celery_tasks.send_otp_sms_task.delay")
    @mock.patch("utils.sms.SMSService.send_otp")
    def test_queue_down_falls_back_to_direct_send_and_shows_error(self, mock_send_otp, mock_delay):
        mock_delay.side_effect = ConnectionError("Celery is down")
        mock_send_otp.return_value = {"success": False, "error": "Direct send failed"}
        client = Client()
        resp = client.post(reverse("accounts:request_otp_login"), {"phone_number": "09151112233"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ارسال پیامک ناموفق بود", resp.content.decode("utf-8"))
        self.assertFalse(OTPCode.objects.filter(phone_number="09151112233").exists())

    @mock.patch("accounts.celery_tasks.send_otp_sms_task.delay")
    @mock.patch("utils.sms.SMSService.send_otp")
    def test_queue_down_but_direct_send_succeeds(self, mock_send_otp, mock_delay):
        mock_delay.side_effect = ConnectionError("Celery is down")
        mock_send_otp.return_value = {"success": True}
        client = Client()
        resp = client.post(reverse("accounts:request_otp_login"), {"phone_number": "09151112233"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("کد", resp.content.decode("utf-8"))
        self.assertTrue(OTPCode.objects.filter(phone_number="09151112233", is_used=False).exists())
        mock_send_otp.assert_called_once_with(mobile="09151112233", code=mock.ANY)

    @override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
    @mock.patch("utils.sms.SMSService.send_otp")
    def test_transient_error_retries_twice_then_gives_up(self, mock_send_otp):
        # returns 503, so it retries max_retries=2 times. Total attempts = 3.
        mock_send_otp.return_value = {"success": False, "http_status": 503, "error": "temp fail"}
        otp, _ = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        
        send_otp_sms_task.apply_async(args=(otp.pk, "09151112233", "12345"))
        
        self.assertEqual(mock_send_otp.call_count, 3)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    @mock.patch("utils.sms.SMSService.send_otp")
    def test_config_error_is_not_retried(self, mock_send_otp):
        # returns without http_status (so not transient) -> call count 1, is_used=True
        mock_send_otp.return_value = {"success": False, "error": "SMS_IR_API_KEY is empty"}
        otp, _ = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        
        send_otp_sms_task.apply(args=(otp.pk, "09151112233", "12345"))
        
        self.assertEqual(mock_send_otp.call_count, 1)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    @mock.patch("utils.sms.SMSService.send_otp")
    def test_success_does_not_touch_otp(self, mock_send_otp):
        mock_send_otp.return_value = {"success": True}
        otp, _ = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        
        send_otp_sms_task.apply(args=(otp.pk, "09151112233", "12345"))
        
        self.assertEqual(mock_send_otp.call_count, 1)
        otp.refresh_from_db()
        self.assertFalse(otp.is_used)

    @mock.patch("utils.sms.SMSService.send_otp")
    def test_raw_code_never_logged(self, mock_send_otp):
        mock_send_otp.return_value = {"success": False, "error": "SMS failed"}
        otp, _ = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        
        # Check that '12345' is never printed in any logs produced during send_otp_sms_task
        with self.assertLogs(level="DEBUG") as cm:
            send_otp_sms_task.apply(args=(otp.pk, "09151112233", "12345"))
        
        all_logs = "".join(cm.output)
        self.assertNotIn("12345", all_logs)
