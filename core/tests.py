from datetime import timedelta
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from accounts.models import User, OTPCode
from core.models import Specialty, Location, Party
from projects.models import Project
from notifications.models import Notification, NotificationPolicy, ChannelPolicy, NotificationType
from utils.image_utils import optimize_image


class CoreAndPartyTests(TestCase):
    def test_party_individual_validation(self):
        party = Party(name="علی رضایی", entity_type=Party.EntityType.INDIVIDUAL, is_client=True)
        with self.assertRaises(ValidationError):
            party.clean()
        party.national_code = "0012345678"
        party.clean()

    def test_party_company_validation(self):
        party = Party(name="شرکت تهویه فرابخش", entity_type=Party.EntityType.COMPANY, is_partner=True)
        with self.assertRaises(ValidationError):
            party.clean()
        party.company_registration_number = "12345"
        party.clean()

    def test_party_requires_at_least_one_role(self):
        party = Party(name="بدون نقش", entity_type=Party.EntityType.INDIVIDUAL, national_code="0012345678")
        with self.assertRaises(ValidationError):
            party.clean()


class OTPCodeTests(TestCase):
    def test_generate_and_verify(self):
        phone = "09121112233"
        otp, code = OTPCode.generate(phone, OTPCode.Purpose.LOGIN)
        self.assertIsNotNone(otp)
        self.assertEqual(len(code), 5)
        self.assertFalse(otp.is_used)

        # اشتباه
        ok, msg = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, "99999")
        self.assertFalse(ok)

        # درست
        ok, verified_otp = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, code)
        self.assertTrue(ok)
        self.assertTrue(verified_otp.is_used)

    def test_expired_otp(self):
        phone = "09129998877"
        otp, code = OTPCode.generate(phone, OTPCode.Purpose.LOGIN, ttl_minutes=-5)
        ok, msg = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, code)
        self.assertFalse(ok)
        self.assertIn("منقضی", msg)


class ImageOptimizeTests(TestCase):
    def test_already_optimized_webp(self):
        img_io = BytesIO()
        img = Image.new("RGB", (300, 300), color="blue")
        img.save(img_io, format="WEBP")
        img_io.seek(0)
        uploaded = SimpleUploadedFile("test.webp", img_io.read(), content_type="image/webp")
        result = optimize_image(uploaded, profile_name="avatar")
        self.assertIs(result, uploaded)


class LocationAdminMapWidgetTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="loc_admin_test", phone_number="09120000099",
            password="AdminPassword123", role=User.Role.ADMIN,
        )

    @override_settings(NESHAN_API_KEY="")
    def test_add_location_page_shows_warning_without_key(self):
        client = Client(SERVER_NAME='localhost')
        client.force_login(self.admin_user)
        resp = client.get(reverse("admin:core_location_add"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("کلید NESHAN_API_KEY تنظیم نشده", resp.content.decode("utf-8"))

    @override_settings(NESHAN_API_KEY="test-fake-key-for-render-check")
    def test_add_location_page_shows_map_with_key(self):
        client = Client(SERVER_NAME='localhost')
        client.force_login(self.admin_user)
        resp = client.get(reverse("admin:core_location_add"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("location-map", content)
        self.assertIn("neshan-maplibre-sdk", content)

    def test_location_still_saves_lat_lng_via_plain_post(self):
        client = Client(SERVER_NAME='localhost')
        client.force_login(self.admin_user)
        resp = client.post(reverse("admin:core_location_add"), {
            "title": "دفتر مرکزی",
            "address_text": "",
            "city": "مشهد",
            "latitude": "36.297900",
            "longitude": "59.606200",
        })
        self.assertEqual(resp.status_code, 302)
