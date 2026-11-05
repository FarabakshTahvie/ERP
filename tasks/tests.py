import tempfile
import shutil
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from accounts.models import User
from core.models import Specialty
from notifications.models import Notification, NotificationType
from tasks import services
from utils.test_helpers import make_image_file, make_accountant


class TaskBaseTests(TestCase):
    def setUp(self):
        super().setUp()
        self.manager = User.objects.create_user(username="tmgr", role=User.Role.ADMIN, password="pw")
        self.accountant = make_accountant("tacc")
        self.tech1 = User.objects.create_user(username="09130000011", role=User.Role.EMPLOYEE, password="pw", is_active=True, phone_number="09130000011")
        self.tech2 = User.objects.create_user(username="09130000012", role=User.Role.EMPLOYEE, password="pw", is_active=True, phone_number="09130000012")
        self.inactive = User.objects.create_user(username="09130000013", role=User.Role.EMPLOYEE, password="pw", is_active=False, phone_number="09130000013")
        self.intake = User.objects.create_user(username="tint", role=User.Role.EMPLOYEE, password="pw")
        self.intake.specialties.add(Specialty.objects.get_or_create(name="پذیرش")[0])
        self.client_user = User.objects.create_user(username="tcli", role=User.Role.CLIENT, password="pw")


class TaskAccessTests(TaskBaseTests):
    def test_matrix(self):
        c = Client()
        for user, exp in [(self.manager, 200), (self.accountant, 200), (self.tech1, 404), (self.intake, 404), (self.client_user, 404)]:
            c.force_login(user)
            self.assertEqual(c.get(reverse("tasks:list")).status_code, exp)
            self.assertEqual(c.get(reverse("tasks:open_table")).status_code, exp)
            self.assertEqual(c.get(reverse("tasks:done_table")).status_code, exp)
        anon = Client()
        self.assertEqual(anon.get(reverse("tasks:list")).status_code, 302)

    def test_manager_cannot_see_accountants_task(self):
        t = services.create_task(actor=self.accountant, title="Acc task", assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.manager)
        self.assertEqual(c.get(reverse("tasks:detail", args=[t.pk])).status_code, 404)
        self.assertEqual(c.get(reverse("tasks:edit", args=[t.pk])).status_code, 404)


class TaskServiceTests(TaskBaseTests):
    def test_assignee_validation(self):
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[self.client_user.pk])
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[self.inactive.pk])
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[])


class TaskCheckTests(TaskBaseTests):
    def setUp(self):
        super().setUp()
        self.task = services.create_task(
            actor=self.manager, title="Check task",
            subtasks=[{"pk": None, "title": "S1"}, {"pk": None, "title": "S2"}],
            assignee_ids=[self.tech1.pk]
        )
        self.sub_ids = list(self.task.subtasks.values_list("pk", flat=True))

    def test_non_assignee_gets_json_error(self):
        c = Client()
        c.force_login(self.tech2)
        res = c.post(reverse("tasks:check", args=[self.task.pk]), {"done": "true"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["ok"])

    def test_submit_requires_main_and_locks(self):
        c = Client()
        c.force_login(self.tech1)
        sub = c.post(reverse("tasks:submit", args=[self.task.pk]), {"note": "n"})
        self.assertEqual(sub.status_code, 400)
        c.post(reverse("tasks:check", args=[self.task.pk]), {"done": "true"})
        sub2 = c.post(reverse("tasks:submit", args=[self.task.pk]), {"note": "n"})
        self.assertEqual(sub2.status_code, 200)


class TaskEditTests(TaskBaseTests):
    def test_add_subtask_reopens_and_recomputes(self):
        task = services.create_task(actor=self.manager, title="E", assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.tech1)
        c.post(reverse("tasks:check", args=[task.pk]), {"done": "true"})
        c.post(reverse("tasks:submit", args=[task.pk]), {"note": "ok"})
        # Now manager updates and adds a new subtask
        services.update_task(task, actor=self.manager, title="E", subtasks=[{"pk": None, "title": "New Sub"}], assignee_ids=[self.tech1.pk])
        ass = task.assignments.get(user=self.tech1)
        self.assertIsNone(ass.submitted_at)
        self.assertFalse(ass.main_checked)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TaskAttachmentTests(TaskBaseTests):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_media_access(self):
        img = make_image_file("test.jpg", size=(100, 100), fmt="JPEG")
        task = services.create_task(actor=self.manager, title="Media", assignee_ids=[self.tech1.pk])
        att = services.add_attachment(task, uploaded=img, actor=self.manager)
        c = Client()
        c.force_login(self.tech1)
        self.assertEqual(c.get(att.file.url).status_code, 200)
        c_stranger = Client()
        c_stranger.force_login(self.tech2)
        self.assertEqual(c_stranger.get(att.file.url).status_code, 404)
