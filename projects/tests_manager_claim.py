from datetime import date

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Party, Specialty
from projects.models import Project, ProjectStage, StageEvent, StageKind
from projects.services import claim_stage, create_project_from_technician_intake
from projects.workflow_v3 import build_workflow_v3
from utils.test_helpers import make_accountant


class ManagerClaimBase(TestCase):
    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        mk = User.objects.create_user
        self.manager = mk(username="mc_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("mc_acc")
        spec = Specialty.objects.get_or_create(name="بازدیدکننده")[0]
        self.visitor = mk(username="mc_vis", password="pw", role=User.Role.EMPLOYEE)
        self.visitor.specialties.add(spec)
        self.client_user = mk(username="mc_cli", password="pw", role=User.Role.CLIENT)
        partner = Party.objects.create(name="شریک ادعا", is_partner=True, phone_number="09125550909")
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.accountant, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.stage = self.project.stages.get(kind=StageKind.VISIT)
        self.claim_url = reverse("projects:my_task_claim", args=[self.stage.id])
        self.overview_url = reverse("projects:staff_project_overview", args=[self.project.id])

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c


class ManagerClaimTests(ManagerClaimBase):
    def test_manager_sees_button_claims_and_gets_the_stage(self):
        self.assertTrue(self.stage.candidate_users.filter(pk=self.visitor.pk).exists())
        c = self.login(self.manager)
        self.assertContains(c.get(self.overview_url), self.claim_url)
        resp = c.post(self.claim_url)
        self.assertRedirects(resp, reverse("projects:my_task_detail", args=[self.stage.id]))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.manager)
        self.assertFalse(self.stage.candidate_users.exists())
        self.assertTrue(StageEvent.objects.filter(stage=self.stage, actor=self.manager, comment="کار را برداشت.").exists())
        self.assertNotContains(c.get(self.overview_url), self.claim_url)

    def test_stage_without_owner_or_pool_is_claimable_by_manager_only(self):
        self.stage.candidate_users.clear()
        self.assertContains(self.login(self.manager).get(self.overview_url), self.claim_url)
        self.assertNotContains(self.login(self.accountant).get(self.overview_url), self.claim_url)

    def test_assigned_stage_cannot_be_taken(self):
        claim_stage(self.stage, self.visitor)
        c = self.login(self.manager)
        self.assertNotContains(c.get(self.overview_url), self.claim_url)
        c.post(self.claim_url)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.visitor)

    def test_manager_can_complete_the_claimed_stage(self):
        c = self.login(self.manager)
        c.post(self.claim_url)
        resp = c.post(reverse("projects:my_task_complete", args=[self.stage.id]), {"comment": "بازدید انجام شد"})
        self.assertRedirects(resp, reverse("home"))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.DONE)
        self.assertEqual(self.project.stages.get(kind=StageKind.PROFORMA).status, ProjectStage.Status.IN_PROGRESS)

    def test_cancelled_project_cannot_be_claimed(self):
        Project.objects.filter(pk=self.project.pk).update(status=Project.Status.CANCELLED)
        c = self.login(self.manager)
        self.assertNotContains(c.get(self.overview_url), self.claim_url)
        c.post(self.claim_url)
        self.stage.refresh_from_db()
        self.assertIsNone(self.stage.assigned_to)

    def test_existing_rules_still_hold(self):
        self.login(self.accountant).post(self.claim_url)       # حسابدار کاندیدا نیست
        self.stage.refresh_from_db()
        self.assertIsNone(self.stage.assigned_to)
        self.assertEqual(self.login(self.client_user).post(self.claim_url).status_code, 302)   # مشتری راه ندارد
        self.stage.refresh_from_db()
        self.assertIsNone(self.stage.assigned_to)
        self.login(self.visitor).post(self.claim_url)           # کاندیدای استخر همچنان برمی‌دارد
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.visitor)


class NewProjectButtonTests(ManagerClaimBase):
    def test_manager_and_accountant_get_the_button_and_the_form(self):
        url = reverse("projects:new_project_form")
        for user in (self.manager, self.accountant):
            c = self.login(user)
            self.assertContains(c.get(reverse("home")), url, msg_prefix=user.username)
            self.assertEqual(c.get(url).status_code, 200, user.username)

    def test_plain_technician_gets_neither(self):
        url = reverse("projects:new_project_form")
        c = self.login(self.visitor)
        self.assertNotContains(c.get(reverse("home")), url)
        self.assertEqual(c.get(url).status_code, 302)

