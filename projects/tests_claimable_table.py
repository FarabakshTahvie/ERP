from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from core.models import Party
from accounts.models import User
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate
from utils.jalali import jalali_str

class ClaimableTableDateTests(TestCase):
    def setUp(self):
        self.tech = User.objects.create_user(username="tech", role=User.Role.EMPLOYEE)
        self.client = Party.objects.create(name="مشتری", is_client=True)
        self.template = WorkflowTemplate.objects.create(name="قالب", is_default=True)
        self.step1 = WorkflowStepTemplate.objects.create(template=self.template, title="مرحله ۱", order=1)
        self.step2 = WorkflowStepTemplate.objects.create(template=self.template, title="مرحله ۲", order=2)
        
        # پروژه‌ها
        self.proj1 = Project.objects.create(name="نخستین پروژه", status=Project.Status.IN_PROGRESS, created_by=self.tech, partner=self.client)
        self.proj2 = Project.objects.create(name="دومین پروژه", status=Project.Status.IN_PROGRESS, created_by=self.tech, partner=self.client)
        
        # مراحل
        self.stage1 = ProjectStage.objects.create(project=self.proj1, step_template=self.step1, status=ProjectStage.Status.IN_PROGRESS, started_at=timezone.now() - timedelta(days=5), order=1)
        self.stage1.candidate_users.add(self.tech)
        
        self.stage2 = ProjectStage.objects.create(project=self.proj2, step_template=self.step1, status=ProjectStage.Status.IN_PROGRESS, started_at=timezone.now() - timedelta(days=1), order=1)
        self.stage2.candidate_users.add(self.tech)
        
        self.web = Client()
        self.web.force_login(self.tech)
        
        self.url = reverse("projects:dashboard_claimable_table")

    def test_table_displays_dates(self):
        resp = self.web.get(self.url)
        self.assertContains(resp, jalali_str(self.stage1.started_at, fmt="%Y/%m/%d %H:%M"))
        self.assertContains(resp, jalali_str(self.stage2.started_at, fmt="%Y/%m/%d %H:%M"))

    def test_table_sorting(self):
        # Asc
        resp = self.web.get(self.url, {"cl_sort": "started_at", "cl_dir": "asc"})
        content = resp.content.decode()
        self.assertTrue(content.index("نخستین پروژه") < content.index("دومین پروژه"))
        
        # Desc
        resp = self.web.get(self.url, {"cl_sort": "started_at", "cl_dir": "desc"})
        content = resp.content.decode()
        self.assertTrue(content.index("دومین پروژه") < content.index("نخستین پروژه"))

    def test_table_filtering(self):
        from_date = jalali_str(self.stage2.started_at, fmt="%Y/%m/%d")
        resp = self.web.get(self.url, {"cl_ffrom_date": from_date})
        self.assertContains(resp, "دومین پروژه")
        self.assertNotContains(resp, "نخستین پروژه")

    def test_none_started_at(self):
        self.stage1.started_at = None
        self.stage1.save()
        resp = self.web.get(self.url)
        self.assertContains(resp, "—")
