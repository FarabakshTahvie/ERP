import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from projects.models import Project, ProjectStage, StageKind, ProjectFile
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake, advance_stage
from projects.stage_ops import add_stage_file, set_cut, cuts_summary


class StageFilesAndViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09121112233")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.creator = User.objects.create_user(username="creator_v", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.other_tech = User.objects.create_user(username="other_v", password="pw", role=User.Role.EMPLOYEE)
        self.admin = User.objects.create_user(username="admin_v", password="pw", role=User.Role.ADMIN, is_staff=True)

        build_workflow_v2(make_default=True)
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
        resp = self.client.post(url, {"file": SimpleUploadedFile("test.png", b"filecontent")})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()["ok"])

        # Success upload
        self.client.force_login(self.creator)
        resp = self.client.post(url, {"file": SimpleUploadedFile("test.png", b"filecontent")})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["name"], "test.png")

    def test_cut_set_view(self):
        # Create gcode stage and file with cut_count=3
        gcode_stage = self.project.stages.get(kind=StageKind.GCODE)
        gcode_file = ProjectFile.objects.create(
            stage=gcode_stage, file=SimpleUploadedFile("cut.nc", b"gcode"),
            kind=ProjectFile.Kind.GCODE, original_name="cut.nc",
            uploaded_by=self.creator, is_attachment=True, cut_count=3
        )
        # Set cutting stage to in_progress and assigned_to creator
        cutting_stage = self.project.stages.get(kind=StageKind.CUTTING)
        cutting_stage.status = ProjectStage.Status.IN_PROGRESS
        cutting_stage.assigned_to = self.creator
        cutting_stage.save()

        url = reverse("projects:cut_set", args=[gcode_file.id])
        self.client.force_login(self.creator)

        # Set cut index 1 to done
        resp = self.client.post(url, {"index": "1", "done": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["done"], 1)
        self.assertEqual(data["file_done"], 1)

        # Invalid index returns 400
        resp_invalid = self.client.post(url, {"index": "99", "done": "1"})
        self.assertEqual(resp_invalid.status_code, 400)
        self.assertFalse(resp_invalid.json()["ok"])

    def test_new_project_submit_ajax_response(self):
        self.client.force_login(self.creator)
        url = reverse("projects:new_project_submit")

        # Validation error without XHR header (standard redirect to new_project_form)
        resp_no_xhr = self.client.post(url, {
            "party_id": self.partner.id,
            "visit_at": "",
        })
        self.assertEqual(resp_no_xhr.status_code, 302)
        self.assertRedirects(resp_no_xhr, reverse("projects:new_project_form"))

        # Validation error via AJAX
        resp = self.client.post(url, {
            "party_id": self.partner.id,
            "visit_at": "",
        }, **{"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("error", resp.json())

        # Success via AJAX
        resp = self.client.post(url, {
            "party_id": self.partner.id,
            "visit_at": "1405/07/20 10:30",
            "notes": "پروژه ایجکس",
        }, **{"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["redirect"], reverse("home"))
