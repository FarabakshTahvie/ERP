from unittest import mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from notifications.models import Broadcast, Notification
from notifications.broadcast import run_process_broadcasts, _unique_short_codes

User = get_user_model()


class BroadcastEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", phone_number="09121111111", password="pw")
        self.broadcast_push = Broadcast.objects.create(
            channel="push",
            title="Test Push",
            body="Hello",
            is_dry_run=True,
            created_by=self.user
        )
        self.broadcast_sms = Broadcast.objects.create(
            channel="sms",
            title="Test SMS",
            body="Hello SMS",
            is_dry_run=False,
            created_by=self.user
        )

    def test_runs_several_batches_in_one_call(self):
        codes = _unique_short_codes(45)
        n_objs = [
            Notification(
                user=self.user,
                broadcast=self.broadcast_push,
                short_code=codes[i],
                status=Notification.Status.PENDING
            )
            for i in range(45)
        ]
        Notification.objects.bulk_create(n_objs)
        stats = run_process_broadcasts()
        self.assertEqual(stats["finalized"], 45)
        self.assertEqual(Notification.objects.filter(status=Notification.Status.PUSH_SENT).count(), 45)

    @override_settings(SMS_FREE_TEXT_ENABLED=True, NAJVA_ENABLED=True)
    @mock.patch("utils.sms.SMSService.send_text")
    def test_waiting_channel_does_not_loop_or_starve_other_channel(self, mock_send_text):
        mock_send_text.return_value = {"success": False, "http_status": 503, "error": "temp error"}
        
        # SMS rows (lower pks)
        codes_sms = _unique_short_codes(2)
        n_sms = [
            Notification(user=self.user, broadcast=self.broadcast_sms, short_code=codes_sms[i], status=Notification.Status.PENDING)
            for i in range(2)
        ]
        Notification.objects.bulk_create(n_sms)

        # Push rows (higher pks)
        codes_push = _unique_short_codes(3)
        n_push = [
            Notification(user=self.user, broadcast=self.broadcast_push, short_code=codes_push[i], status=Notification.Status.PENDING)
            for i in range(3)
        ]
        Notification.objects.bulk_create(n_push)

        stats = run_process_broadcasts()
        self.assertEqual(stats["waiting"], 1)
        self.assertEqual(stats["finalized"], 3)
        self.assertEqual(Notification.objects.filter(status=Notification.Status.PENDING).count(), 2) # SMS pending
        self.assertEqual(Notification.objects.filter(status=Notification.Status.PUSH_SENT).count(), 3) # Push sent

    @override_settings(SMS_FREE_TEXT_ENABLED=True)
    @mock.patch("utils.sms.SMSService.send_text")
    def test_global_error_fails_remaining_rows_of_that_broadcast(self, mock_send_text):
        mock_send_text.return_value = {"success": False, "http_status": 200, "data": {"status": 102}, "error": "اعتبار"}
        codes = _unique_short_codes(3)
        n_objs = [
            Notification(user=self.user, broadcast=self.broadcast_sms, short_code=codes[i], status=Notification.Status.PENDING)
            for i in range(3)
        ]
        Notification.objects.bulk_create(n_objs)

        stats = run_process_broadcasts()
        self.assertEqual(Notification.objects.filter(status=Notification.Status.FAILED).count(), 3)

    def test_time_budget_sets_more(self):
        codes = _unique_short_codes(45)
        n_objs = [
            Notification(user=self.user, broadcast=self.broadcast_push, short_code=codes[i], status=Notification.Status.PENDING)
            for i in range(45)
        ]
        Notification.objects.bulk_create(n_objs)
        stats = run_process_broadcasts(max_seconds=0)
        self.assertTrue(stats["more"])
        self.assertEqual(Notification.objects.filter(status=Notification.Status.PENDING).count(), 5)

    def test_heartbeat_called_per_row(self):
        codes = _unique_short_codes(3)
        n_objs = [
            Notification(user=self.user, broadcast=self.broadcast_push, short_code=codes[i], status=Notification.Status.PENDING)
            for i in range(3)
        ]
        Notification.objects.bulk_create(n_objs)
        hb = mock.Mock()
        run_process_broadcasts(heartbeat=hb)
        self.assertEqual(hb.call_count, 3)

    def test_command_still_processes_dry_run_rows(self):
        codes = _unique_short_codes(5)
        n_objs = [
            Notification(user=self.user, broadcast=self.broadcast_push, short_code=codes[i], status=Notification.Status.PENDING)
            for i in range(5)
        ]
        Notification.objects.bulk_create(n_objs)
        call_command("process_broadcasts")
        self.assertEqual(Notification.objects.filter(status=Notification.Status.PUSH_SENT).count(), 5)
