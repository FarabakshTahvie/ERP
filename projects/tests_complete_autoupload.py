from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Party
from projects.models import ProjectStage
from projects.services import create_project_from_technician_intake
from projects.workflow_v3 import build_workflow_v3


class CompleteFormAutoUploadTests(TestCase):
    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        partner = Party.objects.create(name="شریک بارگذاری", is_partner=True, phone_number="09125550101")
        self.tech = User.objects.create_user(username="au_tech", password="pw", role=User.Role.EMPLOYEE)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.stage = self.project.stages.get(order=1)
        self.stage.assigned_to = self.tech
        self.stage.save()
        self.client.force_login(self.tech)

    def test_overview_marks_complete_form_and_has_dropzone(self):
        resp = self.client.get(reverse("projects:staff_project_overview", args=[self.project.id]))
        self.assertContains(resp, "data-complete-form")
        self.assertContains(resp, "data-complete-error")
        self.assertContains(resp, "data-dropzone")

    def test_script_uploads_pending_files_before_submit(self):
        text = (Path(settings.BASE_DIR) / "templates" / "projects" / "staff_project_overview.html").read_text(encoding="utf-8")
        self.assertIn("uploadAll(zone.dataset.url)", text)
        self.assertIn("requestSubmit", text)
        self.assertIn("_uploadsDone", text)

    def test_completing_without_pending_files_still_works(self):
        resp = self.client.post(reverse("projects:my_task_complete", args=[self.stage.id]), {"comment": "تمام شد"})
        self.assertEqual(resp.status_code, 302)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.DONE)
