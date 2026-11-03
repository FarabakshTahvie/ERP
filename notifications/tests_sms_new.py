"""تست‌های send_shipment_sent و send_install_done در SMSService."""
from unittest import mock

from django.test import TestCase

from utils.sms import SMSService, fit_param, SMS_PARAM_MAX


POST_PATH = "utils.sms.SMSService._post"
OK = {"success": True, "message_id": 1}


class SendShipmentSentTests(TestCase):
    def test_calls_send_pattern_with_correct_args(self):
        svc = SMSService()
        with mock.patch.object(svc, "send_pattern", return_value=OK) as m:
            result = svc.send_shipment_sent(mobile="09120000001", name="علی", project="پروژه ۱", link="s/abc")
        m.assert_called_once_with("09120000001", "shipment_sent", NAME="علی", PROJECT="پروژه ۱", LINK="s/abc")
        self.assertEqual(result, OK)

    def test_posts_to_sms_ir(self):
        svc = SMSService()
        with mock.patch(POST_PATH, return_value=OK) as m:
            svc.send_shipment_sent(mobile="09120000001", name="علی", project="پروژه", link="s/abc")
        args = m.call_args
        payload = args[0][1]
        self.assertEqual(payload["templateId"], 521186)
        param_names = [p["name"] for p in payload["parameters"]]
        self.assertIn("NAME", param_names)
        self.assertIn("PROJECT", param_names)
        self.assertIn("LINK", param_names)


class SendInstallDoneTests(TestCase):
    def test_calls_send_pattern_with_correct_args(self):
        svc = SMSService()
        with mock.patch.object(svc, "send_pattern", return_value=OK) as m:
            result = svc.send_install_done(mobile="09120000001", name="رضا", project="پروژه نصب", link="s/xyz")
        m.assert_called_once_with("09120000001", "install_done", NAME="رضا", PROJECT="پروژه نصب", LINK="s/xyz")
        self.assertEqual(result, OK)

    def test_posts_to_sms_ir(self):
        svc = SMSService()
        with mock.patch(POST_PATH, return_value=OK) as m:
            svc.send_install_done(mobile="09120000001", name="رضا", project="پروژه", link="s/xyz")
        args = m.call_args
        payload = args[0][1]
        self.assertEqual(payload["templateId"], 275534)
        param_names = [p["name"] for p in payload["parameters"]]
        self.assertIn("NAME", param_names)
        self.assertIn("PROJECT", param_names)
        self.assertIn("LINK", param_names)


class FitParamSmsTests(TestCase):
    def test_long_project_name_trimmed_to_limit(self):
        long_name = "پروژه فرابخش تهویه کویر مرکزی اصفهان بزرگ"
        result = fit_param(long_name, limit=SMS_PARAM_MAX)
        self.assertLessEqual(len(result), SMS_PARAM_MAX)

    def test_fit_param_no_trailing_space(self):
        result = fit_param("ab cd ef gh ij kl mn op", limit=10)
        self.assertFalse(result.endswith(" "))
