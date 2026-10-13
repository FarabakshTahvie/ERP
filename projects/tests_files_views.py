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

    def test_group_cut_set_view(self):
        from projects.models import FileGroup
        gcode_stage = self.project.stages.get(kind=StageKind.GCODE)
        group = FileGroup.objects.create(project=self.project, stage=gcode_stage, title="طبقه اول")
        ProjectFile.objects.create(
            stage=gcode_stage, group=group, file=SimpleUploadedFile("cut.nc", b"gcode"),
            kind=ProjectFile.Kind.GCODE, original_name="cut.nc",
            uploaded_by=self.creator, is_attachment=True, cut_count=3
        )
        cutting_stage = self.project.stages.get(kind=StageKind.CUTTING)
        cutting_stage.status = ProjectStage.Status.IN_PROGRESS
        cutting_stage.assigned_to = self.creator
        cutting_stage.save()

        url = reverse("projects:group_cut_set", args=[group.id])
        self.client.force_login(self.creator)
        resp = self.client.post(url, {"done": "1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual((data["total"], data["done"]), (1, 1))
        group.refresh_from_db()
        self.assertTrue(group.cut_done)

        resp = self.client.post(url, {"done": "0"})
        self.assertEqual(resp.json()["done"], 0)

        self.client.force_login(self.other_tech)
        resp_other = self.client.post(url, {"done": "1"})
        self.assertEqual(resp_other.status_code, 400)
        self.assertFalse(resp_other.json()["ok"])

    def test_new_project_submit_ajax_response(self):
        self.client.force_login(self.creator)
        url = reverse("projects:new_project_submit")

        # Validation error without XHR header (standard redirect to new_project_form)
        resp_no_xhr = self.client.post(url, {
            "project_name": "پروژه‌ی آزمایشی",
            "party_id": self.partner.id,
            "visit_date": "",
        })
        self.assertEqual(resp_no_xhr.status_code, 302)
        self.assertRedirects(resp_no_xhr, reverse("projects:new_project_form"))

        # Validation error via AJAX
        resp = self.client.post(url, {
            "project_name": "پروژه‌ی آزمایشی",
            "party_id": self.partner.id,
            "visit_date": "",
        }, **{"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["ok"])
        self.assertIn("error", resp.json())

        # Success via AJAX
        resp = self.client.post(url, {
            "project_name": "پروژه‌ی آزمایشی",
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
        build_workflow_v3(make_default=True)
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
        from projects.models import FileGroup
        FileGroup.objects.create(project=self.project, stage=gcode_stage, title="طبقه اول")
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
        resp = client.post(url, {"file": make_image_file("site.jpg")},
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
        build_workflow_v3(make_default=True)
        client = Client()
        client.force_login(creator)
        resp = client.post(reverse("projects:new_project_submit"), {
            "project_name": "پروژه‌ی آزمایشی",
            "party_id": party.id, "visit_date": "1405/07/20",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["upload_url"])
        up_resp = client.post(data["upload_url"], {"file": make_image_file("map.jpg")},
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(up_resp.status_code, 200)
        self.assertTrue(up_resp.json()["ok"])
