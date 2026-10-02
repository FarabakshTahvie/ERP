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
            "visit_date": "",
        })
        self.assertEqual(resp_no_xhr.status_code, 302)
        self.assertRedirects(resp_no_xhr, reverse("projects:new_project_form"))

        # Validation error via AJAX
        resp = self.client.post(url, {
            "party_id": self.partner.id,
            "visit_date": "",
        }, **{"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("error", resp.json())

        # Success via AJAX
        resp = self.client.post(url, {
            "party_id": self.partner.id,
            "visit_date": "1405/07/20",
            "notes": "پروژه ایجکس",
        }, **{"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(resp.json()["redirect"], reverse("home"))


class StageFileUploadUrlRegressionTests(TestCase):
    """رگرسیون باگ: include بدون url/is_gcode/anchor → data-url خالی می‌ماند."""

    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست آپلود", is_partner=True, phone_number="09121113344")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.creator = User.objects.create_user(username="up_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)
        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )
        self.stage = self.project.stages.get(order=1)
        self.stage.assigned_to = self.creator
        self.stage.save()

    def test_dropzone_url_is_not_empty_and_points_to_upload_endpoint(self):
        client = Client()
        client.force_login(self.creator)
        resp = client.get(reverse("projects:staff_project_overview", args=[self.project.id]))
        content = resp.content.decode("utf-8")
        expected_url = reverse("projects:stage_file_upload", args=[self.stage.id])
        self.assertIn(f'data-url="{expected_url}"', content)
        self.assertNotIn('data-url=""', content)

    def test_gcode_stage_dropzone_has_cuts_flag(self):
        gcode_stage = self.project.stages.get(kind=StageKind.GCODE)
        gcode_stage.status = ProjectStage.Status.IN_PROGRESS
        gcode_stage.assigned_to = self.creator
        gcode_stage.save()
        client = Client()
        client.force_login(self.creator)
        resp = client.get(reverse("projects:staff_project_overview", args=[self.project.id]))
        content = resp.content.decode("utf-8")
        gcode_upload_url = reverse("projects:stage_file_upload", args=[gcode_stage.id])
        idx = content.find(f'data-url="{gcode_upload_url}"')
        self.assertNotEqual(idx, -1)
        self.assertIn('data-cuts="1"', content[idx:idx + 150])

    def test_upload_actually_succeeds_end_to_end(self):
        client = Client()
        client.force_login(self.creator)
        url = reverse("projects:stage_file_upload", args=[self.stage.id])
        resp = client.post(url, {"file": SimpleUploadedFile("site.jpg", b"x", content_type="image/jpeg")},
                            HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])


class NewProjectUploaderScriptRegressionTests(TestCase):
    """رگرسیون باگ: uploader.js روی صفحه‌ی ثبت پروژه جدید لود نمی‌شد."""

    def test_new_project_form_loads_uploader_js(self):
        sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        creator = User.objects.create_user(username="np_creator", password="pw", role=User.Role.EMPLOYEE)
        creator.specialties.add(sp_intake)
        client = Client()
        client.force_login(creator)
        resp = client.get(reverse("projects:new_project_form"))
        content = resp.content.decode("utf-8")
        self.assertRegex(content, r'<script\s+src="[^"]*js/uploader\.js')
        self.assertIn("data-dropzone", content)
        self.assertIn("data-deferred-upload", content)

    def test_deferred_upload_flow_end_to_end(self):
        sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        creator = User.objects.create_user(username="np_creator2", password="pw", role=User.Role.EMPLOYEE)
        creator.specialties.add(sp_intake)
        party = Party.objects.create(name="کارفرمای آپلود جدید", phone_number="09121114455", is_client=True)
        build_workflow_v2(make_default=True)
        client = Client()
        client.force_login(creator)
        resp = client.post(reverse("projects:new_project_submit"), {
            "party_id": party.id, "visit_date": "1405/07/20",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["upload_url"])
        up_resp = client.post(data["upload_url"], {"file": SimpleUploadedFile("map.jpg", b"x", content_type="image/jpeg")},
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(up_resp.status_code, 200)
        self.assertTrue(up_resp.json()["ok"])
