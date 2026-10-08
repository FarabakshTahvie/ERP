import os
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User
from messenger import cleanup, media, services
from messenger.celery_tasks import cleanup_old_task
from messenger.models import Attachment, Conversation, Message, Profile
from messenger.tests import Base
from messenger.tests_media import MediaBase
from notifications.models import Notification, NotificationType
from tasks import services as task_services
from tasks.models import Task
from utils.models import PushDevice
from utils.test_helpers import make_image_file


class RenameTests(Base):
    def test_old_title_is_healed_by_inbox(self):
        Conversation.objects.filter(pk=self.main.pk).update(title="فراگرام")
        item = services.inbox(self.t1)["items"][0]
        self.assertEqual((item["key"], item["title"]), ("main", "فرابخش گروه"))
        self.assertEqual(services.MAIN_TITLE, "فرابخش گروه")


class ProfileTests(MediaBase):
    def test_display_name_replaces_real_name_everywhere(self):
        services.update_profile(self.t1, display_name="  علی   رضایی ", handle="")
        msg = self.send(self.t1, self.main, "x")
        data = services.fetch_messages(self.t2, self.main)
        self.assertEqual(data["messages"][-1]["sender"]["name"], "علی رضایی")
        item = next(i for i in services.inbox(self.manager)["items"] if i["key"] == f"u{self.t1.pk}")
        self.assertEqual(item["title"], "علی رضایی")
        self.assertIn("علی رضایی", services.push_payload(msg)[0])
        services.update_profile(self.t1, display_name="", handle="")
        self.assertEqual(services.display_name(User.objects.get(pk=self.t1.pk)), "ms_t1")

    def test_handle_rules(self):
        p = services.update_profile(self.t1, display_name="", handle="@Ali_95")
        self.assertEqual(p.handle, "ali_95")
        for bad in ("ab", "1abc", "a-b-c", "x" * 25, "علی"):
            with self.assertRaises(ValueError, msg=bad):
                services.update_profile(self.t1, display_name="", handle=bad)
        with self.assertRaises(ValueError):
            services.update_profile(self.t2, display_name="", handle="ALI_95")
        with self.assertRaises(ValueError):
            services.update_profile(self.t1, display_name="ن" * 41, handle="")
        services.update_profile(self.t1, display_name="", handle="")
        services.update_profile(self.t2, display_name="", handle="ali_95")

    def test_avatar_is_square_webp_visible_to_staff_only(self):
        services.set_avatar(self.t1, make_image_file("me.jpg", size=(900, 600), fmt="JPEG"))
        url = services.avatar_url(User.objects.get(pk=self.t1.pk))
        self.assertTrue(url)
        with Image.open(Profile.objects.get(user=self.t1).avatar.path) as im:
            self.assertEqual((im.format, im.size), ("WEBP", (512, 512)))
        for u in (self.t2, self.manager):
            self.assertEqual(self.login(u).get(url).status_code, 200, u.username)
        self.assertEqual(self.login(self.cli).get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 302)

    def test_replacing_and_removing_deletes_old_file(self):
        services.set_avatar(self.t1, make_image_file("a.png", size=(300, 300)))
        first = Profile.objects.get(user=self.t1).avatar.path
        services.set_avatar(self.t1, make_image_file("b.png", size=(300, 300)))
        second = Profile.objects.get(user=self.t1).avatar.path
        self.assertNotEqual(first, second)
        self.assertFalse(os.path.exists(first))
        self.assertTrue(os.path.exists(second))
        services.remove_avatar(self.t1)
        self.assertFalse(os.path.exists(second))
        self.assertEqual(services.avatar_url(User.objects.get(pk=self.t1.pk)), "")

    def test_bad_avatar_rejected(self):
        big = make_image_file("big.png", size=(50, 50))
        big.size = media.MAX_AVATAR_BYTES + 1
        for f in (SimpleUploadedFile("x.jpg", b"not an image"), SimpleUploadedFile("x.exe", b"MZ"), big, None):
            with self.assertRaises(ValueError):
                services.set_avatar(self.t1, f)

    def test_inbox_and_chat_meta_expose_avatar_and_handle(self):
        services.set_avatar(self.acc, make_image_file("c.png", size=(300, 300)))
        services.update_profile(self.acc, display_name="", handle="acc_boss")
        acc = User.objects.get(pk=self.acc.pk)
        item = next(i for i in services.inbox(self.t1)["items"] if i["key"] == f"u{self.acc.pk}")
        self.assertEqual((item["avatar"], item["handle"]), (services.avatar_url(acc), "acc_boss"))
        conv = services.open_direct(self.t1, self.acc)
        self.assertEqual(services.chat_meta(self.t1, conv)["avatar"], item["avatar"])

    def test_profile_page_and_post_flow(self):
        url = reverse("messenger:profile")
        self.assertEqual(self.login(self.cli).get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 302)
        c = self.login(self.t1)
        self.assertEqual(c.get(url).status_code, 200)
        r = c.post(url, {"action": "info", "display_name": "نام نو", "handle": "new_h"})
        self.assertRedirects(r, url, fetch_redirect_response=False)
        self.assertEqual(Profile.objects.get(user=self.t1).handle, "new_h")
        bad = c.post(url, {"action": "info", "display_name": "نام", "handle": "!!"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "!!")


class CleanupTests(MediaBase):
    def age(self, msg, days=200):
        Message.objects.filter(pk=msg.pk).update(created_at=timezone.now() - timedelta(days=days))

    def test_old_messages_and_files_go_new_and_pinned_stay(self):
        att = self.att(self.t1, self.main, self.doc())
        old = self.send_files(self.t1, self.main, [att], text="old")
        path = att.file.path
        pinned = self.send(self.t1, self.main, "pinned")
        services.set_pinned(self.t1, pinned.pk, True)
        fresh = self.send(self.t2, self.main, "fresh")
        self.age(old)
        self.age(pinned)
        self.assertEqual(cleanup.purge_old(), 1)
        self.assertFalse(Message.objects.filter(pk=old.pk).exists())
        self.assertFalse(Attachment.objects.filter(pk=att.pk).exists())
        self.assertFalse(os.path.exists(path))
        self.assertEqual(Message.objects.filter(pk__in=[pinned.pk, fresh.pk]).count(), 2)

    def test_last_message_is_refreshed(self):
        conv = services.open_direct(self.t1, self.acc)
        a, b = self.send(self.t1, conv, "a"), self.send(self.t1, conv, "b")
        self.age(b)
        cleanup.purge_old()
        conv.refresh_from_db()
        self.assertEqual(conv.last_message_id, a.pk)
        self.age(a)
        cleanup.purge_old()
        conv.refresh_from_db()
        self.assertIsNone(conv.last_message_id)
        self.assertIsNone(conv.last_message_at)

    def test_other_apps_data_is_untouched(self):
        old = timezone.now() - timedelta(days=400)
        n = Notification.objects.create(user=self.t1, notification_type=NotificationType.MANUAL, title="t", body="b")
        Notification.objects.filter(pk=n.pk).update(created_at=old)
        task = task_services.create_task(actor=self.manager, title="old task", assignee_ids=[self.t1.pk])
        Task.objects.filter(pk=task.pk).update(created_at=old)
        self.age(self.send(self.t1, self.main, "x"))
        cleanup.purge_old()
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_beat_entry_and_task_run(self):
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE["messenger-cleanup"]["task"], "messenger.cleanup_old")
        m = self.send(self.t1, self.main, "x")
        self.age(m)
        cleanup_old_task.apply()
        self.assertFalse(Message.objects.filter(pk=m.pk).exists())


class TasksChatTests(Base):
    def make(self, title, user=None):
        return task_services.create_task(actor=self.manager, title=title, assignee_ids=[(user or self.t1).pk])

    def finish(self, task, user):
        task_services.set_check(task_id=task.pk, user=user, done=True)
        task_services.submit_assignment(task_id=task.pk, user=user, note="ok")

    def tasks_item(self, user):
        return next(i for i in services.inbox(user)["items"] if i["key"] == "tasks")

    def test_inbox_item_counts_pending_only_and_is_second(self):
        a = self.make("الف")
        self.make("ب")
        items = services.inbox(self.t1)["items"]
        self.assertEqual([items[0]["key"], items[1]["key"]], ["main", "tasks"])
        self.assertEqual(self.tasks_item(self.t1)["unread"], 2)
        self.finish(a, self.t1)
        self.assertEqual(self.tasks_item(self.t1)["unread"], 1)
        self.assertEqual(services.inbox(self.t1)["total_unread"], services.unread_total(self.t1))
        self.assertEqual(self.tasks_item(self.manager)["unread"], 0)

    def test_tasks_page_access_and_content(self):
        self.make("کار امروز")
        url = reverse("messenger:tasks")
        r = self.login(self.t1).get(url)
        self.assertContains(r, "کار امروز")
        self.assertContains(r, 'data-active-key="tasks"')
        self.assertContains(r, reverse("messenger:tasks_done_table"))
        self.assertRedirects(self.login(self.manager).get(url), reverse("tasks:list"), fetch_redirect_response=False)
        self.assertEqual(self.login(self.cli).get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 302)

    def test_done_table_lists_only_own_finished_tasks(self):
        mine = self.make("تمام‌شده")
        self.make("در جریان")
        theirs = self.make("مال دیگری", user=self.t2)
        self.finish(mine, self.t1)
        self.finish(theirs, self.t2)
        html = self.login(self.t1).get(reverse("messenger:tasks_done_table")).content.decode("utf-8")
        self.assertIn("تمام‌شده", html)
        for other in ("در جریان", "مال دیگری"):
            self.assertNotIn(other, html)

    def test_detail_only_for_the_assignee(self):
        t = self.make("جزئیات")
        url = reverse("messenger:task_detail", args=[t.pk])
        self.assertContains(self.login(self.t1).get(url), "جزئیات")
        self.assertEqual(self.login(self.t2).get(url).status_code, 404)
        self.assertEqual(self.login(self.cli).get(url).status_code, 404)

    def test_home_completed_tab_no_longer_shows_tasks_but_open_ones_stay(self):
        done = self.make("وظیفه‌ی انجام‌شده‌ی صفحه")
        self.finish(done, self.t1)
        c = self.login(self.t1)
        resp = c.get("/", {"tab": "completed"})
        self.assertNotIn("وظیفه‌ی انجام‌شده‌ی صفحه", resp.content.decode("utf-8"))
        tabs = {t["key"]: t for t in resp.context["tabs"]["tabs"]}
        self.assertEqual(tabs["completed"]["count"], 0)
        self.make("وظیفه‌ی باز")
        self.assertContains(c.get("/"), "وظیفه‌ی باز")


class NotifyGuideTests(Base):
    def test_center_page_has_status_card_and_modal(self):
        PushDevice.objects.create(user=self.t1, registration_id=str(uuid.uuid4()))
        html = self.login(self.t1).get(reverse("notifications:center")).content.decode("utf-8")
        for marker in ("data-notify-guide", 'data-devices="1"', "data-notify-dialog", "data-notify-open", "notify_guide.js"):
            self.assertIn(marker, html)
        form_end = html.index("</form>", html.index("همه دیده شد"))
        self.assertGreater(html.index("data-notify-dialog"), form_end)       # مودال بیرون از فرم
        none = self.login(self.t2).get(reverse("notifications:center")).content.decode("utf-8")
        self.assertIn('data-devices="0"', none)


class M4SourceTests(SimpleTestCase):
    def test_media_preload_and_assets(self):
        base = Path(settings.BASE_DIR)
        js = (base / "static" / "js" / "messenger_media.js").read_text(encoding="utf-8")
        self.assertIn("a.preload = 'metadata'", js)
        self.assertNotIn("preload = 'none'", js)
        css = (base / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn('@source "../js/notify_guide.js";', css)
        sprite = (base / "static" / "icons" / "sprite.svg").read_text(encoding="utf-8")
        for icon in ("user", "check-square", "info"):
            self.assertRegex(sprite, rf'id=["\']{icon}["\']', icon)

    def test_notify_guide_has_no_html_sinks(self):
        text = (Path(settings.BASE_DIR) / "static" / "js" / "notify_guide.js").read_text(encoding="utf-8")
        for word in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(word, text, word)