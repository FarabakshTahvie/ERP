import uuid
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance.models import Invoice
from projects.confirmations import confirmation_path
from projects.models import (
    Project, ProjectFile, ProjectStage,
    StageConfirmation, StageKind, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.ops import final_review_data
from utils.navigation import NON_PAGE, PAGE_PARENTS


def _make_client_with_party(username="vw_cli", party_name="مشتری پرتال"):
    party = Party.objects.create(name=party_name, is_client=True, phone_number="09120000002")
    user = User.objects.create_user(
        username=username, password="pw", role=User.Role.CLIENT,
        party=party, phone_number="09120000002", first_name="مشتری"
    )
    return user, party


def _make_project(partner, owner=None):
    return Project.objects.create(
        name="پروژه تست پرتال", partner=partner,
        owner=owner or partner, status=Project.Status.IN_PROGRESS,
    )


def _make_stage(project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE):
    tpl = WorkflowTemplate.objects.create(name=f"_vw_wf_{kind}_{project.pk}_{status}_{uuid.uuid4().hex[:6]}")
    step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="مرحله پرتال")
    return ProjectStage.objects.create(
        project=project, step_template=step, kind=kind, order=1, title="مرحله پرتال",
        status=status,
    )


class UrlSentinelTests(TestCase):
    def test_confirmation_path_matches_reverse(self):
        stage_id = 99
        self.assertEqual(confirmation_path(stage_id), reverse("projects:portal_stage_confirmation", args=[stage_id]))

    def test_navigation_registration(self):
        self.assertIn("projects:portal_stage_confirmation", PAGE_PARENTS)
        self.assertIn("projects:portal_confirmation_image", NON_PAGE)


class StageConfirmationViewTests(TestCase):
    def setUp(self):
        self.client_user, self.party = _make_client_with_party("sc_client", "شرکت فرابخش تست")
        self.project = _make_project(self.party)
        self.stage = _make_stage(self.project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE)
        self.conf = StageConfirmation.objects.create(stage=self.stage, recipient=self.client_user)

        self.accountant = User.objects.create_user(
            username="sc_acc", password="pw", role=User.Role.ADMIN
        )
        other_party = Party.objects.create(name="دیگری", is_client=True)
        self.other_user = User.objects.create_user(
            username="sc_other", password="pw", role=User.Role.CLIENT, party=other_party
        )

    def test_login_required(self):
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/accounts/login/", res.url)


    def test_unrelated_user_returns_404(self):
        self.client.force_login(self.other_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_non_owner_post_returns_404(self):
        self.client.force_login(self.accountant)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.post(url, {"decision": "received"})
        self.assertEqual(res.status_code, 404)


class ConfirmationImageViewTests(TestCase):
    def setUp(self):
        self.client_user, self.party = _make_client_with_party("ci_client", "مشتری تصویر")
        self.project = _make_project(self.party)
        self.stage = _make_stage(self.project, kind=StageKind.INSTALL, status=ProjectStage.Status.DONE)
        self.conf = StageConfirmation.objects.create(stage=self.stage, recipient=self.client_user)

        self.accountant = User.objects.create_user(
            username="ci_acc", password="pw", role=User.Role.ADMIN
        )
        other_party = Party.objects.create(name="دیگری عکس", is_client=True)
        self.other_user = User.objects.create_user(
            username="ci_other", password="pw", role=User.Role.CLIENT, party=other_party
        )

        f = SimpleUploadedFile("install.jpg", b"\xff\xd8\xff\xe0fake-jpeg-content", content_type="image/jpeg")
        self.file_obj = ProjectFile.objects.create(
            stage=self.stage, file=f, kind=ProjectFile.Kind.IMAGE, is_attachment=True
        )

    def test_image_view_unrelated_returns_404(self):
        self.client.force_login(self.other_user)
        url = reverse("projects:portal_confirmation_image", args=[self.stage.id, self.file_obj.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)


