import os
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from messenger import cleanup, services
from messenger.models import Attachment, Message
from messenger.tests import Base
from messenger.tests_media import MediaBase
from notifications.models import Notification, NotificationType
from tasks import services as task_services
from tasks.models import Task


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


class TasksChatTests(Base):
    def make(self, title, user=None):
        return task_services.create_task(actor=self.manager, title=title, assignee_ids=[(user or self.t1).pk])

    def test_detail_only_for_the_assignee(self):
        t = self.make("جزئیات")
        url = reverse("messenger:task_detail", args=[t.pk])
        self.assertContains(self.login(self.t1).get(url), "جزئیات")
        self.assertEqual(self.login(self.t2).get(url).status_code, 404)
        self.assertEqual(self.login(self.cli).get(url).status_code, 404)
