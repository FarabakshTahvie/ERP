import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

from utils.sms import SMSService
from accounts.models import OTPCode
from notifications.models import Notification, NotificationType, NotificationClickEvent

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

    def test_verify_otp_external_next_becomes_root(self):
        otp, raw_code = OTPCode.generate(phone_number="09151112233", purpose=OTPCode.Purpose.LOGIN)
        resp = Client().post(reverse("accounts:verify_otp_login"),
                             {"phone_number": "09151112233", "code": raw_code, "next": "https://evil.com/"})
        self.assertEqual(resp.headers.get("HX-Redirect"), "/")
