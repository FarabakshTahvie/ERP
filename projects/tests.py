from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Party, Location
from projects.models import Project, WorkflowTemplate, WorkflowStepTemplate, ProjectStage
from projects.services import create_project_stages_from_template, advance_stage

User = get_user_model()


class ProjectWorkflowTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(
            name="شریک تجاری نمونه",
            entity_type=Party.EntityType.COMPANY,
            company_registration_number="112233",
            is_partner=True,
        )
        self.user = User.objects.create_user(username="tech_user", password="password123", role=User.Role.EMPLOYEE)

        # ایجاد قالب ۳ مرحله‌ای با حلقه اصلاح
        self.template = WorkflowTemplate.objects.create(name="قالب تهویه ساختمانی", is_default=True)
        self.step1 = WorkflowStepTemplate.objects.create(
            template=self.template,
            order=1,
            title="بازدید اولیه",
            client_label="بازدید کارشناسی",
        )
        self.step2 = WorkflowStepTemplate.objects.create(
            template=self.template,
            order=2,
            title="طراحی اتوکد",
            client_label="طراحی نقشه اولیه",
        )
        self.step3 = WorkflowStepTemplate.objects.create(
            template=self.template,
            order=3,
            title="تایید طرح توسط کارفرما",
            client_label="تایید نقشه",
            on_reject_go_to=self.step2,  # در صورت رد، برگرد به مرحله طراحی اتوکد
        )

        self.project = Project.objects.create(
            name="برج مسکونی نگین",
            partner=self.partner,
            workflow_template=self.template,
            created_by=self.user,
        )

    def test_project_code_generated(self):
        self.assertTrue(self.project.code.startswith("P"))
        self.assertIn("-", self.project.code)

    def test_create_stages_and_advance(self):
        stages = create_project_stages_from_template(self.project)
        self.assertEqual(len(stages), 3)

        stage1 = stages[0]
        self.assertEqual(stage1.status, ProjectStage.Status.IN_PROGRESS)

        # پیشبرد مرحله ۱ به DONE
        advance_stage(stage1, actor=self.user, new_status=ProjectStage.Status.DONE)
        stage1.refresh_from_db()
        self.assertEqual(stage1.status, ProjectStage.Status.DONE)

        # مرحله ۲ باید خودکار IN_PROGRESS شده باشد
        stage2 = ProjectStage.objects.get(project=self.project, step_template=self.step2)
        self.assertEqual(stage2.status, ProjectStage.Status.IN_PROGRESS)

        # پیشبرد مرحله ۲ به DONE
        advance_stage(stage2, actor=self.user, new_status=ProjectStage.Status.DONE)
        stage3 = ProjectStage.objects.get(project=self.project, step_template=self.step3)
        self.assertEqual(stage3.status, ProjectStage.Status.IN_PROGRESS)

        # رد مرحله ۳ توسط کارفرما: باید مرحله ۲ دوباره IN_PROGRESS شود
        advance_stage(stage3, actor=self.user, new_status=ProjectStage.Status.REJECTED, comment="نقشه اصلاح شود")
        stage3.refresh_from_db()
        stage2.refresh_from_db()
        self.assertEqual(stage3.status, ProjectStage.Status.REJECTED)
        self.assertEqual(stage3.rejection_count, 1)
        self.assertEqual(stage2.status, ProjectStage.Status.IN_PROGRESS)
