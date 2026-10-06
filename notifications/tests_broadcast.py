import uuid
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
from utils.models import PushDevice
from core.models import Specialty
from notifications.models import Broadcast, Notification, NotificationPolicy, NotificationType
from notifications.broadcast import (
    resolve_audience,
    validate_link,
    calculate_digest,
    create_broadcast,
    retry_failed,
    MAX_PUSH_RECIPIENTS,
    MAX_SMS_RECIPIENTS,
)

User = get_user_model()


class BroadcastSystemTests(TestCase):
    def setUp(self):
        cache.clear()
        self.mgr = User.objects.create_user(
            username="manager_u", phone_number="09121111111", password="password123", is_active=True, role="manager"
        )
        self.acc = User.objects.create_user(
            username="accountant_u", phone_number="09122222222", password="password123", is_active=True, role="employee"
        )
        # تخصیص تخصص حسابداری
        self.spec_acc = Specialty.objects.create(name="حسابدار")
        self.acc.specialties.add(self.spec_acc)

        self.tech = User.objects.create_user(
            username="tech_u", phone_number="09123333333", password="password123", is_active=True, role="employee"
        )
        self.client_u = User.objects.create_user(
            username="client_u", phone_number="09124444444", password="password123", is_active=True, role="client"
        )

    def test_resolve_audience_all_staff(self):
        # پوش (شامل همه بدون فیلتر شماره)
        users = resolve_audience("all_staff", [], "push")
        self.assertIn(self.mgr, users)
        self.assertIn(self.acc, users)
        self.assertIn(self.tech, users)
        self.assertNotIn(self.client_u, users)

    def test_resolve_audience_specialty(self):
        users = resolve_audience("specialty", [self.spec_acc.id], "push")
        self.assertIn(self.acc, users)
        self.assertNotIn(self.tech, users)

    def test_resolve_audience_sms_skips_no_phone(self):
        no_phone_user = User.objects.create_user(
            username="nophone", password="password123", is_active=True, role="employee"
        )
        users = resolve_audience("all_staff", [], "sms")
        self.assertNotIn(no_phone_user, users)

    def test_validate_link(self):
        self.assertTrue(validate_link(""))
        self.assertTrue(validate_link("/notifications/"))
        self.assertFalse(validate_link("https://google.com"))
        self.assertFalse(validate_link("//evil.com"))
        self.assertFalse(validate_link("/invalid_url_not_exists/"))

    @override_settings(SMS_FREE_TEXT_ENABLED=True, NAJVA_ENABLED=True)
    def test_create_broadcast_flow(self):
        digest = calculate_digest("سلام همگی", "all_staff", [], "", "sms")
        b = create_broadcast(
            channel="sms",
            title="تست",
            body="سلام همگی",
            link_path="/notifications/",
            icon_name="",
            image_name="",
            ttl_hours=24,
            audience_kind="all_staff",
            audience_ids=[],
            audience_label="همه",
            created_by=self.mgr,
            is_test=False,
            digest=digest
        )
        self.assertEqual(b.recipients_count, 3)  # mgr, acc, tech دارای شماره تلفن هستند
        self.assertEqual(b.notifications.count(), 3)
        self.assertTrue(b.notifications.filter(status=Notification.Status.PENDING).exists())

    @override_settings(SMS_FREE_TEXT_ENABLED=False, BROADCAST_DRY_RUN=False)
    def test_create_broadcast_disabled_flow_fails(self):
        digest = calculate_digest("سلام", "all_staff", [], "", "sms")
        with self.assertRaises(ValueError):
            create_broadcast(
                channel="sms",
                title="تست",
                body="سلام",
                link_path="",
                icon_name="",
                image_name="",
                ttl_hours=24,
                audience_kind="all_staff",
                audience_ids=[],
                audience_label="همه",
                created_by=self.mgr,
                is_test=False,
                digest=digest
            )

    @override_settings(SMS_FREE_TEXT_ENABLED=True)
    def test_process_pending_notifications_ignores_broadcast(self):
        digest = calculate_digest("سلام همگی", "all_staff", [], "", "sms")
        b = create_broadcast(
            channel="sms",
            title="تست",
            body="سلام همگی",
            link_path="",
            icon_name="",
            image_name="",
            ttl_hours=24,
            audience_kind="all_staff",
            audience_ids=[],
            audience_label="همه",
            created_by=self.mgr,
            is_test=False,
            digest=digest
        )
        from django.core.management import call_command
        # بررسی اینکه دستور process_pending_notifications ردیف‌های PENDING پیام همگانی را لمس نکند
        call_command("process_pending_notifications")
        self.assertEqual(b.notifications.filter(status=Notification.Status.PENDING).count(), 3)

    @override_settings(BROADCAST_DRY_RUN=True)
    def test_process_broadcasts_dry_run(self):
        digest = calculate_digest("سلام همگی", "all_staff", [], "", "sms")
        b = create_broadcast(
            channel="sms",
            title="تست",
            body="سلام همگی",
            link_path="",
            icon_name="",
            image_name="",
            ttl_hours=24,
            audience_kind="all_staff",
            audience_ids=[],
            audience_label="همه",
            created_by=self.mgr,
            is_test=False,
            digest=digest
        )
        from django.core.management import call_command
        call_command("process_broadcasts")
        for notif in b.notifications.all():
            notif.refresh_from_db()
            self.assertEqual(notif.status, Notification.Status.SMS_SENT)
            self.assertEqual(notif.error_text, "آزمایشی")

    def test_capabilities_access(self):
        client = Client()
        # ناشناس ۳۰۲ به لاگین
        resp = client.get(reverse("notifications:broadcast_form"))
        self.assertEqual(resp.status_code, 302)

        # کاربر فاقد قابلیت ۴۰۴
        client.force_login(self.client_u)
        resp = client.get(reverse("notifications:broadcast_form"))
        self.assertEqual(resp.status_code, 404)

        # مدیر مجاز ۲۰۰
        client.force_login(self.mgr)
        resp = client.get(reverse("notifications:broadcast_form"))
        self.assertEqual(resp.status_code, 200)
