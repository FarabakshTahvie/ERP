import uuid
import os
import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from utils.push_notification import NajvaService
from utils.sms import SMSService
from utils.models import PushDevice, DeviceType
from accounts.models import OTPCode
from notifications.models import Notification, NotificationPolicy, ChannelPolicy, NotificationType, NotificationClickEvent
from notifications.services import create_notification, dispatch_notification

User = get_user_model()


class Revision3RegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="rev3user", phone_number="09151112233", password="password123", is_active=True
        )
        self.inactive_user = User.objects.create_user(
            username="inactiveuser", phone_number="09159998877", password="password123", is_active=False
        )

    def test_verify_otp_login_success_and_inactive_check(self):
        otp, raw_code = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        client = Client()

        # تست غیرفعال بودن متد GET
        get_resp = client.get(reverse("accounts:verify_otp_login"))
        self.assertEqual(get_resp.status_code, 405)

        # ارسال کد صحیح برای کاربر فعال
        resp = client.post(
            reverse("accounts:verify_otp_login"),
            {"phone_number": "09151112233", "code": raw_code, "next": "/portal/"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("HX-Redirect"), "/portal/")
        self.assertEqual(int(client.session.get("_auth_user_id")), self.user.pk)

        # تست کاربر غیرفعال
        client.logout()
        otp_in, raw_code_in = OTPCode.generate(phone_number="09159998877", purpose=OTPCode.Purpose.LOGIN)
        resp_in = client.post(
            reverse("accounts:verify_otp_login"),
            {"phone_number": "09159998877", "code": raw_code_in}
        )
        self.assertIn("اطلاعات حساب کاربری یافت نشد", resp_in.content.decode("utf-8"))

    @patch("utils.sms.SMSService.send_otp")
    def test_otp_rate_limit(self, mock_send_otp):
        mock_send_otp.return_value = {"success": True}
        client = Client()
        # درخواست اول
        r1 = client.post(reverse("accounts:request_otp_login"), {"phone_number": "09151112233"})
        self.assertEqual(r1.status_code, 200)

        # درخواست دوم در کمتر از ۶۰ ثانیه
        r2 = client.post(reverse("accounts:request_otp_login"), {"phone_number": "09151112233"})
        self.assertIn("لطفاً ۶۰ ثانیه صبر کنید", r2.content.decode("utf-8"))

    @patch("utils.sms.SMSService.send_otp")
    def test_otp_failure_clears_cooldown(self, mock_send_otp):
        mock_send_otp.return_value = {"success": False, "error": "SMS failed"}
        client = Client()

        resp = client.post(reverse("accounts:request_otp_login"), {"phone_number": "09151112233"})
        self.assertIn("ارسال پیامک ناموفق بود", resp.content.decode("utf-8"))
        # بررسی اینکه cooldown پاک شده و کاربر می‌تواند فوراً دوباره تلاش کند
        self.assertIsNone(cache.get("otp:cooldown:09151112233"))

    def test_push_device_register_csrf_protection(self):
        valid_uuid = str(uuid.uuid4())
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        # ارسال POST بدون داشتن توکن CSRF
        resp = client.post(
            reverse("utils:register_push_device"),
            data={"token": valid_uuid},
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_short_link_slashes_and_events(self):
        notif = Notification.objects.create(
            user=self.user,
            notification_type=NotificationType.MANUAL,
            title="تست",
            body="متن",
            real_target_url="/portal/invoices/1/",
        )
        client = Client()

        # تست هر دو شکل با و بدون اسلش
        url1 = f"/s/{notif.short_code}"
        url2 = f"/s/{notif.short_code}/"

        resp1 = client.get(url1, HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(resp1.status_code, 302)

        resp2 = client.get(url2, HTTP_USER_AGENT="Mozilla/5.0")
        self.assertEqual(resp2.status_code, 302)

        notif.refresh_from_db()
        self.assertEqual(NotificationClickEvent.objects.filter(notification=notif).count(), 2)
        # دیده‌شدن یکبار ثبت می‌شود
        self.assertIsNotNone(notif.seen_at)

        # تست متد HEAD (ربات)
        head_resp = client.head(url1)
        self.assertEqual(head_resp.status_code, 302)

        # کد ناشناخته
        resp_404 = client.get("/s/99999/")
        self.assertEqual(resp_404.status_code, 404)

    def test_sms_service_status_0_returns_false(self):
        with patch("utils.sms.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"status": 0, "message": "خطای اعتبار"}
            mock_post.return_value = mock_resp

            res = SMSService().send_otp("09151112233", "12345")
            self.assertFalse(res["success"])

    def test_service_worker_and_contact_info(self):
        client = Client()
        # تست سرویس‌ورکر
        sw_resp = client.get("/najva-messaging-sw.js")
        self.assertEqual(sw_resp.status_code, 200)
        self.assertTrue(sw_resp.content.decode("utf-8").startswith("importScripts"))
        self.assertNotIn("<?xml", sw_resp.content.decode("utf-8"))

        # تست اطلاعات تماس در صفحه لاگین
        login_resp = client.get(reverse("accounts:login"))
        self.assertIn("۰۵۱-۳۳۸۷-۳۷۳۴", login_resp.content.decode("utf-8"))
        self.assertNotIn("۸۸۸۸۸۸۸۸", login_resp.content.decode("utf-8"))

    def test_najva_switch_in_templates(self):
        client = Client()
        client.force_login(self.user)

        with override_settings(NAJVA_ENABLED=False):
            r_off = client.get(reverse("home"))
            self.assertNotIn("van.najva.com", r_off.content.decode("utf-8"))

        with override_settings(NAJVA_ENABLED=True):
            r_on = client.get(reverse("home"))
            self.assertIn("van.najva.com", r_on.content.decode("utf-8"))

    def test_locmem_cache_in_test_environment(self):
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.locmem.LocMemCache")

    def test_service_worker_reachable_with_must_change_password(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])
        client = Client()
        client.force_login(self.user)
        resp = client.get("/najva-messaging-sw.js")
        self.assertEqual(resp.status_code, 200)

    def test_verify_otp_external_next_becomes_root(self):
        otp, raw_code = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        resp = Client().post(reverse("accounts:verify_otp_login"),
                             {"phone_number": "09151112233", "code": raw_code, "next": "https://evil.com/"})
        self.assertEqual(resp.headers.get("HX-Redirect"), "/")
