from datetime import timedelta
from unittest import mock
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.conf import settings

from accounts.models import User
from core.models import Specialty
from notifications.models import Notification
from notifications import broadcast


@override_settings(BROADCAST_DRY_RUN=True, NAJVA_ENABLED=True, SMS_FREE_TEXT_ENABLED=True)
class BroadcastBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="bmgr", role=User.Role.ADMIN, password="pw", phone_number="09131111111")
        cls.tech1 = User.objects.create_user(username="09131111112", role=User.Role.EMPLOYEE, password="pw", is_active=True, phone_number="09131111112")
        cls.sp = Specialty.objects.get_or_create(name="برق")[0]
        cls.tech1.specialties.add(cls.sp)


class BroadcastShortCodeTests(BroadcastBaseTests):
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
