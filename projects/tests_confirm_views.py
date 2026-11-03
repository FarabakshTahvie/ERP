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

    def test_nonexistent_conf_returns_404(self):
        self.client.force_login(self.client_user)
        res = self.client.get(reverse("projects:portal_stage_confirmation", args=[99999]))
        self.assertEqual(res.status_code, 404)

    def test_unrelated_user_returns_404(self):
        self.client.force_login(self.other_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_owner_get_records_view_and_renders_200(self):
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "projects/portal_stage_confirmation.html")
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.view_count, 1)
        self.assertIsNotNone(self.conf.first_viewed_at)

    def test_accountant_get_is_readonly_and_no_view_record(self):
        self.client.force_login(self.accountant)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["readonly"])
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.view_count, 0)

    def test_owner_post_received_decision_redirects_home_if_no_invoice(self):
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.post(url, {"decision": "received"})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("home"))
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.decision, StageConfirmation.Decision.RECEIVED)

    def test_owner_post_redirects_to_invoice_detail_when_invoice_exists(self):
        inv_uuid = uuid.uuid4()
        Invoice.objects.create(
            project=self.project, billed_party=self.party,
            number="INV-CONF-1", total_amount=1000, uuid=inv_uuid,
            issue_date=timezone.localdate(),
        )
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.post(url, {"decision": "received"})
        self.assertEqual(res.status_code, 302)
        expected_url = reverse("finance:portal_invoice_detail", args=[inv_uuid])
        self.assertEqual(res.url, expected_url)

    def test_owner_post_invalid_decision_redirects_back_with_error(self):
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_stage_confirmation", args=[self.stage.id])
        res = self.client.post(url, {"decision": "confirmed"})  # برای SHIPPING مجاز نیست
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, url)
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.decision, StageConfirmation.Decision.PENDING)

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

    def test_image_view_owner_success(self):
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_confirmation_image", args=[self.stage.id, self.file_obj.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["X-Content-Type-Options"], "nosniff")
        self.assertEqual(res["Cache-Control"], "private, max-age=3600")

    def test_image_view_accountant_success(self):
        self.client.force_login(self.accountant)
        url = reverse("projects:portal_confirmation_image", args=[self.stage.id, self.file_obj.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)

    def test_image_view_unrelated_returns_404(self):
        self.client.force_login(self.other_user)
        url = reverse("projects:portal_confirmation_image", args=[self.stage.id, self.file_obj.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)

    def test_image_view_non_install_stage_returns_404(self):
        shipping_stage = _make_stage(self.project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE)
        StageConfirmation.objects.create(stage=shipping_stage, recipient=self.client_user)
        f = SimpleUploadedFile("ship.jpg", b"img", content_type="image/jpeg")
        pf = ProjectFile.objects.create(stage=shipping_stage, file=f, kind=ProjectFile.Kind.IMAGE, is_attachment=True)
        self.client.force_login(self.client_user)
        url = reverse("projects:portal_confirmation_image", args=[shipping_stage.id, pf.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)


class FinalReviewDataConfirmationTests(TestCase):
    def setUp(self):
        self.client_user, self.party = _make_client_with_party("fr_client", "مشتری بازبینی")
        self.project = _make_project(self.party)
        self.stage = _make_stage(self.project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE)
        self.conf = StageConfirmation.objects.create(stage=self.stage, recipient=self.client_user)

    def test_final_review_data_attaches_client_confirm(self):
        data = final_review_data(self.project)
        matching = [s for s in data["stages"] if s.pk == self.stage.pk]
        self.assertEqual(len(matching), 1)
        self.assertIsNotNone(matching[0].client_confirm)
        self.assertEqual(matching[0].client_confirm.pk, self.conf.pk)
