from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Specialty, Party, Location
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate
from projects.services import create_project_stages_from_template, claim_stage, transfer_stage
from catalog.models import Service
from finance.models import Invoice, Payment
from finance.forms import PaymentInlineForm


class TechnicianTasksTests(TestCase):
    def setUp(self):
        self.sp_cnc, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
        self.sp_assembler, _ = Specialty.objects.get_or_create(name="مونتاژکار")

        self.tech1 = User.objects.create_user(
            username="tech1", phone_number="09120000081",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech1.specialties.add(self.sp_cnc)

        self.tech2 = User.objects.create_user(
            username="tech2", phone_number="09120000082",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech2.specialties.add(self.sp_cnc)

        self.tech_other = User.objects.create_user(
            username="tech_other", phone_number="09120000083",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech_other.specialties.add(self.sp_assembler)

        self.partner = Party.objects.create(name="همکار", is_partner=True, national_code="1111111111")
        self.template = WorkflowTemplate.objects.create(name="قالب تست", is_default=True)
        self.step = WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="جی‌کدگیری",
            responsible_specialty=self.sp_cnc,
        )
        self.project = Project.objects.create(
            name="پروژه تست کارهای من", partner=self.partner,
            workflow_template=self.template,
        )
        self.stages = create_project_stages_from_template(self.project)
        self.stage = self.stages[0]



    def test_claim_stage(self):
        self.stage.candidate_users.add(self.tech1)
        client = Client()
        client.force_login(self.tech1)
        resp = client.post(reverse("projects:my_task_claim", args=[self.stage.id]))
        self.assertRedirects(resp, reverse("projects:my_task_detail", args=[self.stage.id]))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.tech1)

    def test_transfer_stage_to_same_specialty(self):
        self.stage.assigned_to = self.tech1
        self.stage.save()

        client = Client()
        client.force_login(self.tech1)
        resp = client.post(reverse("projects:my_task_transfer", args=[self.stage.id]), {
            "target_user": self.tech2.id,
            "comment": "انتقال به همکار",
        })
        self.assertRedirects(resp, reverse("home"))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.tech2)

    def test_transfer_stage_to_different_specialty_fails(self):
        self.stage.assigned_to = self.tech1
        self.stage.save()

        with self.assertRaises(ValueError):
            transfer_stage(self.stage, from_user=self.tech1, to_user=self.tech_other, comment="خطا")






