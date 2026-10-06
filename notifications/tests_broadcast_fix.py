import tempfile
import shutil
from datetime import datetime, timedelta
from unittest import mock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from accounts.models import User
from core.models import Specialty
from notifications.models import Notification, NotificationType, Broadcast
from notifications import broadcast
from utils.test_helpers import make_image_file


@override_settings(BROADCAST_DRY_RUN=True, NAJVA_ENABLED=True, SMS_FREE_TEXT_ENABLED=True)
class BroadcastBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="bmgr", role=User.Role.ADMIN, password="pw", phone_number="09131111111")
        cls.tech1 = User.objects.create_user(username="09131111112", role=User.Role.EMPLOYEE, password="pw", is_active=True, phone_number="09131111112")
        cls.sp = Specialty.objects.get_or_create(name="برق")[0]
        cls.tech1.specialties.add(cls.sp)


class BroadcastShortCodeTests(BroadcastBaseTests):
    def test_every_notification_has_unique_code(self):
        b = broadcast.create_broadcast(
            channel="push", title="T", body="B", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="/notifications/", audience_kind="all_staff", audience_ids=[], created_by=self.manager, is_test=True
        )
        notifs = list(b.notifications.all())
        self.assertGreater(len(notifs), 0)
        codes = [n.short_code for n in notifs]
        self.assertEqual(len(codes), len(set(codes)))
        for n in notifs:
            self.assertTrue(n.short_code)
            self.assertTrue(n.tracking_url.startswith(settings.SITE_BASE_URL))

    @mock.patch("notifications.broadcast.NajvaService.send", return_value={"success": True, "request_id": 123})
    def test_click_tracking_works(self, mock_najva):
        b = broadcast.create_broadcast(
            channel="push", title="T", body="B", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="/notifications/", audience_kind="all_staff", audience_ids=[], created_by=self.manager, is_test=True
        )
        n = b.notifications.first()
        c = Client()
        res = c.get(n.tracking_url, HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')
        self.assertEqual(res.status_code, 302)
        n.refresh_from_db()
        self.assertIsNotNone(n.seen_at)
        self.assertEqual(n.click_events.count(), 1)


class BroadcastDigestTests(BroadcastBaseTests):
    def test_roundtrip_and_tamper(self):
        users = broadcast.resolve_audience("all_staff", [], "push")
        digest = broadcast.calculate_digest(
            channel="push", title="T", body="B", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="/", audience_kind="all_staff", audience_ids=[], resolved_user_ids=[u.pk for u in users]
        )
        b = broadcast.create_broadcast(
            channel="push", title="T", body="B", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="/", audience_kind="all_staff", audience_ids=[], created_by=self.manager, digest=digest
        )
        self.assertGreater(b.notifications.count(), 0)
        with self.assertRaises(ValueError):
            broadcast.create_broadcast(
                channel="push", title="Tampered", body="B", ttl_hours=24, image_name="", icon_name="", buttons=[],
                link_path="/", audience_kind="all_staff", audience_ids=[], created_by=self.manager, digest=digest
            )

    def test_two_digit_specialty_id(self):
        s12 = Specialty.objects.create(id=12, name="تخصصی ۱۲")
        self.tech1.specialties.add(s12)
        users = broadcast.resolve_audience(kind="specialty", ids=[str(s12.id)], channel="push")
        self.assertIn(self.tech1, users)


class BroadcastViewsTests(BroadcastBaseTests):
    def test_form_has_new_fields_and_no_legacy(self):
        c = Client()
        c.force_login(self.manager)
        res = c.get(reverse("notifications:broadcast_form"))
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("audience_specialties", content)
        self.assertIn("audience_roles", content)
        self.assertIn("audience_users", content)
        self.assertNotIn("audience_ids", content)

    @mock.patch("notifications.broadcast.NajvaService.send", return_value={"success": True, "request_id": 1})
    def test_edit_action_returns_filled_form(self, mock_najva):
        c = Client()
        c.force_login(self.manager)
        res = c.post(reverse("notifications:broadcast_preview"), {"action": "edit", "title": "Draft Title", "body": "Draft Body"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Draft Title", res.content.decode("utf-8"))

    def test_error_rerenders_with_values(self):
        c = Client()
        c.force_login(self.manager)
        res = c.post(reverse("notifications:broadcast_preview"), {"action": "preview", "title": "", "body": ""})
        self.assertEqual(res.status_code, 200)

    def test_detail_shows_content(self):
        b = broadcast.create_broadcast(
            channel="push", title="Detail Title", body="Detail Body", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="/", audience_kind="all_staff", audience_ids=[], created_by=self.manager, is_test=True
        )
        c = Client()
        c.force_login(self.manager)
        res = c.get(reverse("notifications:broadcast_detail", args=[b.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertIn("Detail Title", res.content.decode("utf-8"))


class BroadcastLinkTests(TestCase):
    def test_validate_link(self):
        self.assertTrue(broadcast.validate_link("/"))
        self.assertTrue(broadcast.validate_link("/notifications/"))
        self.assertTrue(broadcast.validate_link("/portal/statement/?x=1"))
        self.assertFalse(broadcast.validate_link("//evil.com"))
        self.assertFalse(broadcast.validate_link("https://x"))
        self.assertFalse(broadcast.validate_link("/a\\b"))
        self.assertFalse(broadcast.validate_link("/no-such/"))
        self.assertFalse(broadcast.validate_link("/has space"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BroadcastAssetTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_icon_png_is_shrunk_under_limit(self):
        img = make_image_file("icon.png", size=(1000, 1000), fmt="PNG")
        saved = broadcast.save_broadcast_asset(img, kind="icon")
        self.assertTrue(saved)

    def test_transparent_image_flattened_white(self):
        img = make_image_file("trans.png", size=(200, 200), fmt="PNG")
        saved = broadcast.save_broadcast_asset(img, kind="image")
        self.assertTrue(saved)


class BroadcastDeliveryTests(TestCase):
    @mock.patch("notifications.broadcast.SMSService")
    @override_settings(BROADCAST_DRY_RUN=True, NAJVA_ENABLED=True, SMS_FREE_TEXT_ENABLED=True)
    def test_sms_network_and_5xx_keep_pending(self, mock_sms_cls):
        mock_sms = mock_sms_cls.return_value
        mock_sms.send_text.return_value = {"success": False, "http_status": 503}
        mgr = User.objects.create_user(username="09132222221", role=User.Role.ADMIN, password="pw", phone_number="09132222221")
        b = broadcast.create_broadcast(
            channel="sms", title="", body="SMS Body", ttl_hours=24, image_name="", icon_name="", buttons=[],
            link_path="", audience_kind="all_staff", audience_ids=[], created_by=mgr, is_test=True
        )
        b.is_dry_run = False
        b.save()
        broadcast.expire_stale()
        from notifications.management.commands.process_broadcasts import Command
        Command().handle()
        n = b.notifications.first()
        self.assertEqual(n.status, Notification.Status.PENDING)


@override_settings(BROADCAST_DRY_RUN=True, NAJVA_ENABLED=True, SMS_FREE_TEXT_ENABLED=True)
class BroadcastExpiryTests(TestCase):
    def test_stale_pending_expires_but_retry_does_not(self):
        mgr = User.objects.create_user(username="09133333331", role=User.Role.ADMIN, password="pw", phone_number="09133333331")
        b = broadcast.create_broadcast(
            channel="push", title="T", body="B", ttl_hours=1, image_name="", icon_name="", buttons=[],
            link_path="", audience_kind="all_staff", audience_ids=[], created_by=mgr, is_test=True
        )
        n = b.notifications.first()
        n.created_at = timezone.now() - timedelta(hours=3)
        n.save()
        count = broadcast.expire_stale()
        self.assertEqual(count, 1)
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.FAILED)
        self.assertEqual(n.error_text, "مهلت ارسال گذشت")
