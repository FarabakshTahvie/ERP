from unittest import mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.cache import cache

from notifications.models import Broadcast, Notification
from notifications.broadcast import (
    create_broadcast,
    calculate_digest,
    resolve_audience,
    retry_failed,
    LOCK_KEY,
)
from notifications.celery_tasks import process_broadcasts_task

User = get_user_model()


@override_settings(BROADCAST_DRY_RUN=True, SMS_FREE_TEXT_ENABLED=True, NAJVA_ENABLED=True)
class BroadcastCeleryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="test_admin", phone_number="09121111111", password="pw", role="manager"
        )

    def _create_sms_broadcast(self):
        users = resolve_audience("all_staff", [], "sms")
        user_ids = [u.id for u in users]
        digest = calculate_digest(
            channel="sms", title="تست", body="سلام", link_path="",
            ttl_hours=24, icon_name="", image_name="", buttons=[],
            audience_kind="all_staff", audience_ids=[], resolved_user_ids=user_ids
        )
        return create_broadcast(
            channel="sms", title="تست", body="سلام", link_path="",
            ttl_hours=24, icon_name="", image_name="", buttons=[],
            audience_kind="all_staff", audience_ids=[], created_by=self.user,
            digest=digest
        )

    def test_nothing_is_sent_before_commit(self):
        b = self._create_sms_broadcast()
        self.assertTrue(Notification.objects.filter(broadcast=b).exists())
        self.assertTrue(
            all(n.status == Notification.Status.PENDING for n in Notification.objects.filter(broadcast=b))
        )

    def test_create_broadcast_triggers_processing_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            b = self._create_sms_broadcast()
        notifications = list(Notification.objects.filter(broadcast=b))
        self.assertTrue(len(notifications) > 0)
        for n in notifications:
            self.assertEqual(n.status, Notification.Status.SMS_SENT)
            self.assertEqual(n.error_text, "آزمایشی")

    def test_retry_failed_triggers_processing(self):
        b = self._create_sms_broadcast()
        Notification.objects.filter(broadcast=b).update(status=Notification.Status.FAILED)
        with self.captureOnCommitCallbacks(execute=True):
            updated = retry_failed(b)
        self.assertTrue(updated > 0)
        for n in Notification.objects.filter(broadcast=b):
            self.assertEqual(n.status, Notification.Status.SMS_SENT)
            self.assertEqual(n.error_text, "آزمایشی")

    def test_redis_down_does_not_break_creation(self):
        with mock.patch("notifications.celery_tasks.process_broadcasts_task.delay", side_effect=ConnectionError("Redis down")):
            with self.assertLogs("notifications.broadcast", level="ERROR") as cm:
                with self.captureOnCommitCallbacks(execute=True):
                    b = self._create_sms_broadcast()
        self.assertTrue(Notification.objects.filter(broadcast=b).exists())
        self.assertTrue(any("process_broadcasts could not be queued" in log for log in cm.output))

    def test_lock_blocks_second_run_and_is_released(self):
        b = self._create_sms_broadcast()
        cache.add(LOCK_KEY, "x", 90)
        res = process_broadcasts_task()
        self.assertIsNone(res)
        # rows should still be pending because lock blocked it
        self.assertTrue(all(n.status == Notification.Status.PENDING for n in Notification.objects.filter(broadcast=b)))
        
        # release manually and run again
        cache.delete(LOCK_KEY)
        process_broadcasts_task()
        self.assertTrue(all(n.status == Notification.Status.SMS_SENT for n in Notification.objects.filter(broadcast=b)))
        self.assertIsNone(cache.get(LOCK_KEY))

    def test_lock_released_when_run_raises(self):
        with mock.patch("notifications.celery_tasks.run_process_broadcasts", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                process_broadcasts_task()
        self.assertIsNone(cache.get(LOCK_KEY))

    def test_more_requeues_itself(self):
        with mock.patch("notifications.celery_tasks.run_process_broadcasts", return_value={"finalized": 1, "waiting": 0, "expired": 0, "more": True}):
            with mock.patch("notifications.celery_tasks.process_broadcasts_task.apply_async") as mock_apply_async:
                process_broadcasts_task()
                mock_apply_async.assert_called_once_with(countdown=1)

    def test_task_and_beat_names_are_registered(self):
        from notifications import celery_tasks
        from config import celery_app
        for name, task_conf in settings.CELERY_BEAT_SCHEDULE.items():
            self.assertIn(task_conf["task"], celery_app.tasks)
        self.assertIn("notifications.process_broadcasts", celery_app.tasks)
