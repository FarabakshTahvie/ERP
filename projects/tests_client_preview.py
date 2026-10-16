from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Party
from projects.models import (
    Project, ProjectFile, ProjectStage, StageKind, WorkflowStepTemplate, WorkflowTemplate,
)


class ClientPreviewPortalTests(TestCase):
    def setUp(self):
        self.party = Party.objects.create(name="مشتری طرح", is_client=True, phone_number="09125558001")
        self.other_party = Party.objects.create(name="مشتری دیگر", is_client=True, phone_number="09125558002")
        mk = User.objects.create_user
        self.owner = mk(username="cp_owner", password="pw", role=User.Role.CLIENT, party=self.party)
        self.stranger = mk(username="cp_str", password="pw", role=User.Role.CLIENT, party=self.other_party)
        tpl = WorkflowTemplate.objects.create(name="قالب نمایش طرح")
        self.step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="طراحی",
                                                        kind=StageKind.DESIGN_INITIAL)
        self.project = Project.objects.create(name="پروژه نمایش", partner=self.party, owner=self.party,
                                              workflow_template=tpl, status=Project.Status.IN_PROGRESS)
        self.stage = self.make_stage(self.project, preview=True)
        self.pdf = self.file("plan.pdf", "pdf")
        self.img = self.file("view.png", "image")
        self.dwg = self.file("plan.dwg", "dwg")
        self.gcode = self.file("cut.nc", "gcode")

    def make_stage(self, project, preview):
        return ProjectStage.objects.create(
            project=project, step_template=self.step, order=1, title="طراحی", kind=StageKind.DESIGN_INITIAL,
            status=ProjectStage.Status.DONE, client_preview=preview)

    def file(self, name, kind, stage=None):
        return ProjectFile.objects.create(stage=stage or self.stage, file=SimpleUploadedFile(name, b"data"),
                                          kind=kind, original_name=name, is_attachment=True)

    def url(self, f):
        return reverse("projects:portal_project_file", args=[f.stage.project_id, f.id])

    def progress(self):
        return reverse("projects:portal_project_progress", args=[self.project.id])

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c



    def test_pdf_and_image_inline_others_attachment_gcode_404(self):
        c = self.login(self.owner)
        for f in (self.pdf, self.img):
            resp = c.get(self.url(f))
            self.assertEqual(resp.status_code, 200)
            self.assertNotIn("attachment", resp["Content-Disposition"])
        self.assertIn("attachment", c.get(self.url(self.dwg))["Content-Disposition"])
        self.assertEqual(c.get(self.url(self.gcode)).status_code, 404)

    def test_stranger_and_anonymous_get_nothing(self):
        self.assertEqual(Client().get(self.url(self.pdf)).status_code, 302)
        self.assertEqual(self.login(self.stranger).get(self.url(self.pdf)).status_code, 404)
        self.assertEqual(self.login(self.stranger).get(self.progress()).status_code, 404)



    def test_file_of_another_project_is_not_served_under_this_project(self):
        other = Project.objects.create(name="پروژه دیگر", partner=self.party, owner=self.party,
                                       workflow_template=self.project.workflow_template,
                                       status=Project.Status.IN_PROGRESS)
        foreign = self.file("secret.pdf", "pdf", stage=self.make_stage(other, preview=True))
        wrong = reverse("projects:portal_project_file", args=[self.project.id, foreign.id])
        self.assertEqual(self.login(self.owner).get(wrong).status_code, 404)
