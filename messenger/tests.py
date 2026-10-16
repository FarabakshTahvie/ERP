import uuid
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.capabilities import can
from messenger import services
from messenger.celery_tasks import send_push_task
from messenger.models import Conversation, Message
from notifications.models import Notification
from utils.models import PushDevice
from utils.test_helpers import make_accountant


class Base(TestCase):
    def setUp(self):
        cache.clear()
        mk = User.objects.create_user
        self.manager = mk(username="ms_mgr", password="pw", role=User.Role.ADMIN)
        self.acc = make_accountant("ms_acc")
        self.t1 = mk(username="ms_t1", password="pw", role=User.Role.EMPLOYEE)
        self.t2 = mk(username="ms_t2", password="pw", role=User.Role.EMPLOYEE)
        self.cli = mk(username="ms_cli", password="pw", role=User.Role.CLIENT)
        self.main = services.ensure_main_group()

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def keys(self, user):
        return [i["key"] for i in services.inbox(user)["items"] if i["key"] != "tasks"]

    def send(self, user, conv, text="x", **kw):
        return services.send_message(user, conv, text=text, **kw)[0]


class AccessTests(Base):
    def test_api_access_matrix(self):
        url = reverse("messenger:api_inbox")
        for user, code in ((self.manager, 200), (self.acc, 200), (self.t1, 200), (self.cli, 404)):
            self.assertEqual(self.login(user).get(url).status_code, code, user.username)
        self.assertEqual(Client().get(url).status_code, 302)

    def test_reach_all_sql_matches_capability(self):
        ids = set(services.reach_all_qs().values_list("pk", flat=True))
        for u in (self.manager, self.acc, self.t1, self.t2):
            self.assertEqual(u.pk in ids, can(u, "messenger.reach_all"), u.username)

    def test_open_direct_rules(self):
        for a, b in ((self.t1, self.t2), (self.t1, self.cli), (self.t1, self.t1)):
            with self.assertRaises(ValueError):
                services.open_direct(a, b)
        c1, c2 = services.open_direct(self.t1, self.acc), services.open_direct(self.acc, self.t1)
        self.assertEqual(c1.pk, c2.pk)
        self.assertLess(c1.user_low_id, c1.user_high_id)

    def test_direct_message_is_private(self):
        conv = services.open_direct(self.t1, self.acc)
        self.send(self.t1, conv, "راز")
        url = reverse("messenger:api_messages", args=[conv.pk])
        self.assertEqual(self.login(self.acc).get(url).status_code, 200)
        for outsider in (self.t2, self.manager, self.cli):
            self.assertEqual(self.login(outsider).get(url).status_code, 404, outsider.username)
        self.assertEqual(self.login(self.t2).post(reverse("messenger:api_send", args=[conv.pk]),
                                                  {"text": "x"}).status_code, 404)


class InboxTests(Base):
    def test_tech_sees_main_manager_accountant_only(self):
        keys = self.keys(self.t1)
        self.assertEqual(keys[0], "main")
        self.assertEqual(set(keys[1:]), {f"u{self.manager.pk}", f"u{self.acc.pk}"})

    def test_inactive_user_disappears_and_cannot_be_messaged(self):
        conv = services.open_direct(self.t1, self.acc)
        User.objects.filter(pk=self.acc.pk).update(is_active=False)
        self.assertNotIn(f"u{self.acc.pk}", self.keys(self.t1))
        with self.assertRaises(ValueError):
            self.send(self.t1, conv, "x")


class SendTests(Base):
    def test_html_is_stored_verbatim_and_returned_as_json(self):
        self.send(self.t1, self.main, "<script>alert(1)</script>")
        resp = self.login(self.t2).get(reverse("messenger:api_messages", args=[self.main.pk]))
        self.assertEqual(resp["Content-Type"].split(";")[0], "application/json")
        self.assertEqual(resp.json()["messages"][0]["text"], "<script>alert(1)</script>")

    def test_client_uid_makes_send_idempotent(self):
        uid = str(uuid.uuid4())
        a, c1 = services.send_message(self.t1, self.main, text="a", client_uid=uid)
        b, c2 = services.send_message(self.t1, self.main, text="a", client_uid=uid)
        self.assertEqual((a.pk, c1, c2), (b.pk, True, False))
        self.assertEqual(Message.objects.count(), 1)

    def test_reply_must_belong_to_same_conversation(self):
        m = self.send(self.t1, self.main, "a")
        conv = services.open_direct(self.t1, self.acc)
        with self.assertRaises(ValueError):
            self.send(self.t1, conv, "b", reply_to_id=m.pk)
        self.send(self.t2, self.main, "c", reply_to_id=m.pk)
        data = services.fetch_messages(self.t1, self.main)
        self.assertEqual(data["messages"][-1]["reply"], {"id": m.pk, "name": "ms_t1", "snippet": "a"})

    def test_rate_limit(self):
        for i in range(services.RATE_LIMIT):
            self.send(self.t1, self.main, f"m{i}")
        with self.assertRaises(ValueError):
            self.send(self.t1, self.main, "extra")


class EditDeleteMuteTests(Base):
    def test_only_sender_edits_within_window(self):
        m = self.send(self.t1, self.main, "old")
        with self.assertRaises(ValueError):
            services.edit_message(self.t2, m.pk, "x")
        services.edit_message(self.t1, m.pk, "new")
        m.refresh_from_db()
        self.assertEqual((m.text, bool(m.edited_at)), ("new", True))
        Message.objects.filter(pk=m.pk).update(created_at=timezone.now() - timedelta(hours=49))
        with self.assertRaises(ValueError):
            services.edit_message(self.t1, m.pk, "later")

    def test_delete_clears_text_and_manager_moderates_group_only(self):
        m1 = self.send(self.t1, self.main, "secret")
        services.delete_message(self.manager, m1.pk)
        m1.refresh_from_db()
        self.assertEqual((m1.is_deleted, m1.text), (True, ""))
        conv = services.open_direct(self.t1, self.acc)
        m2 = self.send(self.t1, conv, "x")
        with self.assertRaises(Http404):
            services.delete_message(self.manager, m2.pk)       # عضو چت نیست
        with self.assertRaises(ValueError):
            services.delete_message(self.acc, m2.pk)           # عضو است ولی فرستنده نیست
        services.delete_message(self.t1, m2.pk)


class PushTests(Base):
    def setUp(self):
        super().setUp()
        self.tok = {}
        for u in (self.manager, self.acc, self.t1, self.t2):
            self.tok[u.pk] = str(uuid.uuid4())
            PushDevice.objects.create(user=u, registration_id=self.tok[u.pk])

    def run_task(self, msg, result=None):
        with override_settings(NAJVA_ENABLED=True), mock.patch("messenger.celery_tasks.NajvaService") as svc:
            svc.return_value.send.return_value = result or {"success": True, "invalid_tokens": []}
            send_push_task.apply(args=(msg.pk,))
            return svc.return_value.send

    def test_push_is_queued_after_commit_and_creates_no_notification(self):
        with mock.patch("messenger.celery_tasks.send_push_task.delay") as delay:
            msg = self.send(self.t1, self.main, "x")
            delay.assert_not_called()
        with mock.patch("messenger.celery_tasks.send_push_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                msg = self.send(self.t1, self.main, "y")
            delay.assert_called_once_with(msg.pk)
        self.assertEqual(Notification.objects.count(), 0)

    def test_queue_down_does_not_break_sending(self):
        with mock.patch("messenger.celery_tasks.send_push_task.delay", side_effect=ConnectionError("down")):
            with self.assertLogs("messenger.services", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    msg = self.send(self.t1, self.main, "x")
        self.assertTrue(Message.objects.filter(pk=msg.pk).exists())

    def test_group_push_skips_sender_and_muted(self):
        services.set_muted(self.t2, self.main, True)
        msg = self.send(self.t1, self.main, "hello")
        send = self.run_task(msg)
        send.assert_called_once()
        self.assertEqual(set(send.call_args.kwargs["subscriber_tokens"]),
                         {self.tok[self.manager.pk], self.tok[self.acc.pk]})
        self.assertIn(services.MAIN_TITLE, send.call_args.kwargs["title"])


class SourceGuardTests(SimpleTestCase):
    def test_no_unsafe_html_sinks_in_messenger_files(self):
        base = Path(settings.BASE_DIR)
        banned = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "|safe", "mark_safe", "eval(")
        files = (list((base / "static" / "js").glob("messenger*.js"))
                 + list((base / "templates" / "messenger").rglob("*.html"))
                 + [p for p in (base / "messenger").glob("*.py") if not p.name.startswith("tests")])
        for path in files:
            text = path.read_text(encoding="utf-8")
            for word in banned:
                self.assertNotIn(word, text, f"{path.name}: {word}")
