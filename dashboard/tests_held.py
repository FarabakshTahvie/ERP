from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party, Specialty
from finance.models import Invoice
from projects.models import Project, ProjectStage, StageKind, WorkflowStepTemplate, WorkflowTemplate
from projects.services import suspend_stage


def SPEC(name):
    return Specialty.objects.get_or_create(name=name)[0]


class HeldDashboardTests(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="dh_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="dh_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(SPEC("حسابدار"))

        self.partner = Party.objects.create(name="شریک تست", is_partner=True, phone_number="09123334455")
        self.tpl = WorkflowTemplate.objects.create(name="قالب تست")
        self.step_fr = WorkflowStepTemplate.objects.create(template=self.tpl, order=10, title="بازبینی نهایی", kind=StageKind.FINAL_REVIEW)

        self.project = Project.objects.create(
            name="پروژه تست", partner=self.partner, workflow_template=self.tpl, status=Project.Status.IN_PROGRESS
        )
        self.stage = ProjectStage.objects.create(
            project=self.project, step_template=self.step_fr, order=10, title="بازبینی نهایی", kind=StageKind.FINAL_REVIEW, status=ProjectStage.Status.IN_PROGRESS
        )

    def test_accountant_access_and_restrictions(self):
        # Accountant can view suspended_page and held_detail (they have view permission or accountant specialty)
        # But cannot resume, cancel, suspend, or restore
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")

        c = Client()
        c.force_login(self.accountant)

        # Access to suspended_page (view only)
        r_page = c.get(reverse("dashboard:suspended"))
        self.assertEqual(r_page.status_code, 200)

        # Access to held_detail (view only)
        r_detail = c.get(reverse("dashboard:held_detail", args=[self.project.id]))
        self.assertEqual(r_detail.status_code, 200)

        # Attempt to resume -> fails with 404 because accountant doesn't have assign capabilities
        r_resume = c.post(reverse("dashboard:suspended_resume", args=[self.stage.id]), {"comment": "حسابدار برگرداند"})
        self.assertEqual(r_resume.status_code, 404)

        # Attempt to cancel -> fails with 404
        r_cancel = c.post(reverse("dashboard:suspended_cancel", args=[self.stage.id]), {"comment": "حسابدار لغو کند"})
        self.assertEqual(r_cancel.status_code, 404)

        # Attempt to restore -> fails with 404
        r_restore = c.post(reverse("dashboard:project_restore", args=[self.project.id]), {"comment": "حسابدار برگرداند از لغو"})
        self.assertEqual(r_restore.status_code, 404)

    def test_manager_actions_and_next_redirect(self):
        # Manager can perform all actions
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")

        c = Client()
        c.force_login(self.manager)

        # Resume with custom next
        next_url = reverse("dashboard:held_detail", args=[self.project.id])
        r = c.post(reverse("dashboard:suspended_resume", args=[self.stage.id]), {"comment": "تایید مدیر", "next": next_url})
        # After resuming the last suspended stage, the project is no longer held (no suspended stages),
        # so held_detail would return 404. Checking status_code 302 and target redirect.
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, next_url)

        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.IN_PROGRESS)

        # Suspend from final review via post
        r_sus = c.post(reverse("dashboard:stage_suspend", args=[self.stage.id]), {"comment": "تعلیق نهایی", "next": next_url})
        self.assertRedirects(r_sus, next_url)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.SUSPENDED)
