import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from utils.test_helpers import make_image_file
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from projects.models import Project, ProjectStage, StageKind, ProjectFile
from projects.workflow_v3 import build_workflow_v3
from projects.services import create_project_from_technician_intake, advance_stage
from projects.stage_ops import add_stage_file


class StageFilesAndViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.creator = User.objects.create_user(username="creator_v", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.other_tech = User.objects.create_user(username="other_v", password="pw", role=User.Role.EMPLOYEE)
        self.admin = User.objects.create_user(username="admin_v", password="pw", role=User.Role.ADMIN, is_staff=True)

        build_workflow_v3(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False,
        )
        self.stage = self.project.stages.first()

    def test_stage_file_upload_view(self):
        url = reverse("projects:stage_file_upload", args=[self.stage.id])

        # GET method not allowed (405)
        self.client.force_login(self.creator)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)

        # Unauthorized user (403)
        self.client.force_login(self.other_tech)
        resp = self.client.post(url, {"file": make_image_file("test.png")})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()["ok"])

        # Success upload
        self.client.force_login(self.creator)
        resp = self.client.post(url, {"file": make_image_file("test.png")})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["name"].endswith(".webp") or data["name"] == "test.png")


