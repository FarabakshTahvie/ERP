from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from core.models import Party, Specialty
from projects.models import (
    Project, ProjectFile, ProjectStage, StageApproval, StageKind, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.stage_ops import stage_completion_problem


class DesignFilesTests(TestCase):
    def setUp(self):
        self.party = Party.objects.create(name="مشتری طرح", is_client=True, phone_number="09125558001")
        self.other_party = Party.objects.create(name="مشتری دیگر", is_client=True, phone_number="09125558002")
        mk = User.objects.create_user
        self.owner = mk(username="df_owner", password="pw", role=User.Role.CLIENT, party=self.party)
        self.stranger = mk(username="df_str", password="pw", role=User.Role.CLIENT, party=self.other_party)
        self.accountant = mk(username="df_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        tpl = WorkflowTemplate.objects.create(name="قالب طرح")
        s1 = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="طراحی", kind=StageKind.DESIGN_INITIAL)
        s2 = WorkflowStepTemplate.objects.create(template=tpl, order=2, title="تایید طرح", kind=StageKind.DESIGN_APPROVAL,
                                                 approval_by=WorkflowStepTemplate.ApprovalBy.PARTNER)
        self.project = Project.objects.create(name="پروژه طرح", partner=self.party, owner=self.party,
                                              workflow_template=tpl, status=Project.Status.IN_PROGRESS)
        self.design = ProjectStage.objects.create(project=self.project, step_template=s1, order=1, title="طراحی",
                                                  kind=StageKind.DESIGN_INITIAL, status=ProjectStage.Status.DONE)
        self.approval_stage = ProjectStage.objects.create(
            project=self.project, step_template=s2, order=2, title="تایید طرح", kind=StageKind.DESIGN_APPROVAL,
            status=ProjectStage.Status.WAITING_APPROVAL)
        self.approval = StageApproval.objects.create(stage=self.approval_stage, sent_to_party=self.party)

    def file(self, name, kind, stage=None):
        return ProjectFile.objects.create(stage=stage or self.design, file=SimpleUploadedFile(name, b"data"),
                                          kind=kind, original_name=name, is_attachment=True)

    def url(self, f):
        return reverse("projects:portal_stage_file", args=[self.approval.id, f.id])

    def test_owner_sees_viewable_files_and_download_is_inline_for_pdf(self):
        pdf = self.file("plan.pdf", "pdf")
        c = Client(); c.force_login(self.owner)
        resp = c.get(self.url(pdf))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("attachment", resp["Content-Disposition"])
        page = c.get(reverse("projects:portal_stage_approval", args=[self.approval.id]))
        self.assertContains(page, self.url(pdf))

    def test_stranger_anonymous_and_internal_files_get_nothing(self):
        pdf, gcode = self.file("plan.pdf", "pdf"), self.file("cut.nc", "gcode")
        c = Client()
        self.assertEqual(c.get(self.url(pdf)).status_code, 302)
        c.force_login(self.stranger)
        self.assertEqual(c.get(self.url(pdf)).status_code, 404)
        c.force_login(self.owner)
        self.assertEqual(c.get(self.url(gcode)).status_code, 404)
        elsewhere = self.file("x.pdf", "pdf", stage=self.approval_stage)
        self.assertEqual(c.get(self.url(elsewhere)).status_code, 404)

    def test_accountant_can_view_and_dwg_is_attachment(self):
        dwg = self.file("plan.dwg", "dwg")
        c = Client(); c.force_login(self.accountant)
        resp = c.get(self.url(dwg))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp["Content-Disposition"])

    def test_designer_needs_viewable_file_to_send_for_approval(self):
        self.design.status = ProjectStage.Status.IN_PROGRESS
        self.design.save()
        self.file("plan.dwg", "dwg")
        problem = stage_completion_problem(self.design, needs_approval=True)
        self.assertIn("عکس یا PDF", problem)
        self.assertIsNone(stage_completion_problem(self.design, needs_approval=False))
        self.file("preview.pdf", "pdf")
        self.assertIsNone(stage_completion_problem(self.design, needs_approval=True))
