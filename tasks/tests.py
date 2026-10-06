import tempfile
import shutil
from datetime import datetime, timedelta
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

from accounts.models import User
from core.models import Specialty
from notifications.models import Notification, NotificationType
from tasks.models import Task, TaskAssignment, TaskAttachment, TaskSubtask
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
    def test_create_ok_and_notifies_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            t = services.create_task(
                actor=self.manager, title="New task", description="Desc",
                subtasks=[{"pk": None, "title": "Sub 1"}],
                assignee_ids=[self.tech1.pk, self.tech2.pk]
            )
        self.assertEqual(t.title, "New task")
        self.assertEqual(t.subtasks.count(), 1)
        self.assertEqual(t.assignments.count(), 2)
        self.assertEqual(Notification.objects.filter(notification_type=NotificationType.TASK_ASSIGNED).count(), 2)

    def test_assignee_validation(self):
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[self.client_user.pk])
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[self.inactive.pk])
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", assignee_ids=[])

    def test_due_rules(self):
        with self.assertRaises(ValueError):
            services.create_task(actor=self.manager, title="T", due_at=timezone.now() - timedelta(days=1), assignee_ids=[self.tech1.pk])
        with self.assertRaises(ValueError):
            services.build_due("۱۴۰۵/۰۷/۲۰", "25", "0")
        self.assertIsNone(services.build_due("", "", ""))

    def test_parse_subtasks_keeps_error_message(self):
        with self.assertRaises(ValueError) as ctx:
            services.parse_subtasks('[{"title": ""}]')
        self.assertIn("عنوان", str(ctx.exception))
        self.assertIsNone(services.parse_subtasks(None))


class TaskCheckTests(TaskBaseTests):
    def setUp(self):
        super().setUp()
        self.task = services.create_task(
            actor=self.manager, title="Check task",
            subtasks=[{"pk": None, "title": "S1"}, {"pk": None, "title": "S2"}],
            assignee_ids=[self.tech1.pk]
        )
        self.sub_ids = list(self.task.subtasks.values_list("pk", flat=True))

    def test_subtask_ticks_drive_main(self):
        c = Client()
        c.force_login(self.tech1)
        res = c.post(reverse("tasks:check", args=[self.task.pk]), {"subtask_id": self.sub_ids[0], "done": "true"}).json()
        self.assertTrue(res["ok"])
        self.assertFalse(res["main_checked"])
        res2 = c.post(reverse("tasks:check", args=[self.task.pk]), {"subtask_id": self.sub_ids[1], "done": "true"}).json()
        self.assertTrue(res2["main_checked"])

    def test_main_tick_selects_all_and_untick_clears(self):
        c = Client()
        c.force_login(self.tech1)
        res = c.post(reverse("tasks:check", args=[self.task.pk]), {"done": "true"}).json()
        self.assertTrue(res["main_checked"])
        self.assertEqual(len(res["checked"]), 2)
        res2 = c.post(reverse("tasks:check", args=[self.task.pk]), {"done": "false"}).json()
        self.assertFalse(res2["main_checked"])
        self.assertEqual(len(res2["checked"]), 0)

    def test_task_without_subtasks(self):
        t2 = services.create_task(actor=self.manager, title="No subs", assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.tech1)
        res = c.post(reverse("tasks:check", args=[t2.pk]), {"done": "true"}).json()
        self.assertTrue(res["ok"])
        sub = c.post(reverse("tasks:submit", args=[t2.pk]), {"note": "Done"})
        self.assertEqual(sub.status_code, 200)

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


class TaskProgressTests(TaskBaseTests):
    def test_progress_is_per_assignee(self):
        task = services.create_task(actor=self.manager, title="P", assignee_ids=[self.tech1.pk, self.tech2.pk])
        c1 = Client()
        c1.force_login(self.tech1)
        c1.post(reverse("tasks:check", args=[task.pk]), {"done": "true"})
        c1.post(reverse("tasks:submit", args=[task.pk]), {"note": "ok"})
        # manager open table still has it because tech2 hasn't submitted
        c_mgr = Client()
        c_mgr.force_login(self.manager)
        self.assertIn(task.title, c_mgr.get(reverse("tasks:open_table")).content.decode("utf-8"))


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

    def test_big_image_becomes_webp(self):
        img = make_image_file("test.jpg", size=(3000, 2000), fmt="JPEG")
        task = services.create_task(actor=self.manager, title="Attach", assignee_ids=[self.tech1.pk])
        att = services.add_attachment(task, uploaded=img, actor=self.manager)
        self.assertTrue(att.original_name.endswith(".webp"))
        self.assertTrue(att.is_image)

    def test_pdf_untouched_and_limits(self):
        pdf = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 test content", content_type="application/pdf")
        task = services.create_task(actor=self.manager, title="Attach", assignee_ids=[self.tech1.pk])
        att = services.add_attachment(task, uploaded=pdf, actor=self.manager)
        self.assertEqual(att.original_name, "doc.pdf")
        fake = SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")
        with self.assertRaises(ValueError):
            services.add_attachment(task, uploaded=fake, actor=self.manager)

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


class TaskPanelTests(TaskBaseTests):
    def test_home_tab_contains_cards_and_table(self):
        task = services.create_task(actor=self.manager, title="Home Task", subtasks=[{"pk": None, "title": "S"}], assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.tech1)
        res = c.get("/")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("Home Task", content)
        self.assertIn("حتماً دکمه‌ی «ثبت» را بزنید", content)

    def test_table_endpoint_returns_only_table(self):
        task = services.create_task(actor=self.manager, title="Home Task", assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.tech1)
        res = c.get(reverse("tasks:my_panel"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("Home Task", res.content.decode("utf-8"))


class TaskTablesTests(TaskBaseTests):
    def test_creator_scope_and_search(self):
        t1 = services.create_task(actor=self.manager, title="Alpha task", assignee_ids=[self.tech1.pk])
        acc2 = make_accountant("acc2")
        t2 = services.create_task(actor=acc2, title="Beta task", assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.manager)
        content = c.get(reverse("tasks:open_table") + "?tko_search=Alpha").content.decode("utf-8")
        self.assertIn("Alpha task", content)
        self.assertNotIn("Beta task", content)


class TaskPagesTests(TaskBaseTests):
    def test_pages_render(self):
        task = services.create_task(actor=self.manager, title="Page Task", subtasks=[{"pk": None, "title": "S"}], assignee_ids=[self.tech1.pk])
        c = Client()
        c.force_login(self.manager)
        self.assertEqual(c.get(reverse("tasks:list")).status_code, 200)
        self.assertEqual(c.get(reverse("tasks:detail", args=[task.pk])).status_code, 200)
        self.assertEqual(c.get(reverse("tasks:edit", args=[task.pk])).status_code, 200)
