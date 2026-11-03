"""تست‌های مربوط به StageConfirmation، open_confirmation، set_decision و توابع کمکی."""
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from catalog.models import Service
from core.models import Party
from projects.confirmations import (
    confirmation_path,
    install_images,
    is_recipient_party,
    open_confirmation,
    record_view,
    set_decision,
    shipped_services,
)
from projects.models import (
    Project, ProjectFile, ProjectService, ProjectStage,
    StageConfirmation, StageKind, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.stage_ops import complete_stage
from utils.sms import fit_param


# ─────────────────────────── کمکی ───────────────────────────

_step_tpl_cache = {}


def _get_step_template():
    """یک WorkflowStepTemplate مشترک برای تمام تست‌ها (ساخته می‌شود یا کش می‌شود)."""
    if "tpl" not in _step_tpl_cache:
        wt = WorkflowTemplate.objects.create(name="_conf_test_wf")
        st = WorkflowStepTemplate.objects.create(template=wt, order=1, title="مرحله آزمایش")
        _step_tpl_cache["tpl"] = st
    return _step_tpl_cache["tpl"]

def _make_manager(username="conf_mgr"):
    return User.objects.create_user(username=username, password="pw", role=User.Role.ADMIN)


def _make_client_with_party(username="conf_cli", party_name="مشتری تایید"):
    party = Party.objects.create(name=party_name, is_client=True, phone_number="09120000001")
    user = User.objects.create_user(
        username=username, password="pw", role=User.Role.CLIENT,
        party=party, phone_number="09120000001", first_name="تست"
    )
    return user, party


def _make_project(partner, owner=None, status=Project.Status.IN_PROGRESS):
    return Project.objects.create(
        name="پروژه تایید مشتری", partner=partner,
        owner=owner or partner, status=status,
    )


def _make_stage(project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE):
    tpl = WorkflowTemplate.objects.create(name=f"_wf_{kind}_{project.pk}_{status}")
    step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="مرحله آزمایشی")
    return ProjectStage.objects.create(
        project=project, step_template=step, kind=kind, order=1, title="مرحله‌ی آزمایشی",
        status=status,
    )


# ─────────────────────────── fit_param ───────────────────────────

class FitParamTests(TestCase):
    def test_short_value_unchanged(self):
        self.assertEqual(fit_param("کوتاه"), "کوتاه")

    def test_value_exactly_at_limit_unchanged(self):
        text = "a" * 25
        self.assertEqual(fit_param(text, limit=25), text)

    def test_long_value_cut_at_word_boundary(self):
        result = fit_param("سلام دنیا خوبی", limit=8)
        self.assertLessEqual(len(result), 8)
        self.assertNotIn(" ", result.strip()[-1:])  # آخرین کاراکتر فاصله نیست

    def test_no_space_cut_hard(self):
        result = fit_param("abcdefghij", limit=5)
        self.assertEqual(result, "abcde")

    def test_none_returns_empty(self):
        self.assertEqual(fit_param(None), "")

    def test_extra_spaces_normalized(self):
        result = fit_param("  سلام   دنیا  ")
        self.assertEqual(result, "سلام دنیا")

    def test_exactly_25_chars(self):
        text = "x" * 25
        self.assertEqual(fit_param(text), text)

    def test_26_chars_no_space_cut_hard(self):
        text = "y" * 26
        self.assertEqual(fit_param(text), "y" * 25)


# ─────────────────────────── confirmation_path ───────────────────────────

class ConfirmationPathTests(TestCase):
    def test_path_format(self):
        self.assertEqual(confirmation_path(42), "/portal/stage-confirmations/42/")


# ─────────────────────────── is_recipient_party ───────────────────────────

class IsRecipientPartyTests(TestCase):
    def setUp(self):
        self.client_user, self.party = _make_client_with_party("irp_cli", "طرف‌حساب")
        self.project = _make_project(self.party)

    def test_billing_party_user_returns_true(self):
        self.assertTrue(is_recipient_party(self.client_user, self.project))

    def test_other_user_returns_false(self):
        other_party = Party.objects.create(name="دیگری", is_client=True)
        other_user = User.objects.create_user(
            username="irp_other", password="pw", role=User.Role.CLIENT, party=other_party
        )
        self.assertFalse(is_recipient_party(other_user, self.project))

    def test_user_without_party_returns_false(self):
        manager = _make_manager("irp_mgr")
        self.assertFalse(is_recipient_party(manager, self.project))


# ─────────────────────────── open_confirmation ───────────────────────────

class OpenConfirmationTests(TestCase):
    def setUp(self):
        call_command("setup_notification_policies", stdout=StringIO())
        self.client_user, self.party = _make_client_with_party("oc_cli", "طرف‌حساب تایید")
        self.project = _make_project(self.party)

    def _shipping_stage(self, status=ProjectStage.Status.IN_PROGRESS):
        return _make_stage(self.project, kind=StageKind.SHIPPING, status=status)

    def _install_stage(self, status=ProjectStage.Status.IN_PROGRESS):
        return _make_stage(self.project, kind=StageKind.INSTALL, status=status)

    def test_non_confirm_kind_returns_none(self):
        stage = _make_stage(self.project, kind=StageKind.CUTTING)
        result = open_confirmation(stage)
        self.assertIsNone(result)

    def test_shipping_creates_confirmation(self):
        stage = self._shipping_stage()
        with mock.patch("notifications.services.SMSService.send_shipment_sent", return_value={"success": True, "message_id": 1}):
            with self.captureOnCommitCallbacks(execute=True):
                conf = open_confirmation(stage)
        self.assertIsNotNone(conf)
        self.assertIsInstance(conf, StageConfirmation)
        self.assertEqual(conf.stage, stage)
        self.assertEqual(conf.recipient, self.client_user)
        self.assertEqual(conf.decision, StageConfirmation.Decision.PENDING)

    def test_install_creates_confirmation(self):
        stage = self._install_stage()
        with mock.patch("notifications.services.SMSService.send_install_done", return_value={"success": True, "message_id": 1}):
            with self.captureOnCommitCallbacks(execute=True):
                conf = open_confirmation(stage)
        self.assertIsNotNone(conf)
        self.assertEqual(conf.stage.kind, StageKind.INSTALL)

    def test_idempotent_second_call_no_new_record(self):
        stage = self._shipping_stage()
        with mock.patch("notifications.services.SMSService.send_shipment_sent", return_value={"success": True, "message_id": 1}):
            with self.captureOnCommitCallbacks(execute=True):
                conf1 = open_confirmation(stage)
                conf2 = open_confirmation(stage)
        self.assertEqual(conf1.pk, conf2.pk)
        self.assertEqual(StageConfirmation.objects.filter(stage=stage).count(), 1)

    def test_no_user_no_notification(self):
        """پروژه بدون طرف‌حساب دارای کاربر فعال: تایید ساخته می‌شود اما اعلان نمی‌رود."""
        party_no_user = Party.objects.create(name="بدون کاربر", is_client=True)
        project = _make_project(party_no_user)
        stage = _make_stage(project, kind=StageKind.SHIPPING)
        conf = open_confirmation(stage)
        self.assertIsNotNone(conf)
        self.assertIsNone(conf.recipient)


# ─────────────────────────── record_view ───────────────────────────

class RecordViewTests(TestCase):
    def setUp(self):
        _, party = _make_client_with_party("rv_cli", "طرف‌حساب ویو")
        project = _make_project(party)
        stage = _make_stage(project, kind=StageKind.SHIPPING)
        self.conf = StageConfirmation.objects.create(stage=stage)

    def test_first_view_sets_timestamps(self):
        record_view(self.conf)
        self.conf.refresh_from_db()
        self.assertIsNotNone(self.conf.first_viewed_at)
        self.assertIsNotNone(self.conf.last_viewed_at)
        self.assertEqual(self.conf.view_count, 1)

    def test_second_view_increments_count_not_first_viewed_at(self):
        record_view(self.conf)
        self.conf.refresh_from_db()
        first = self.conf.first_viewed_at
        record_view(self.conf)
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.view_count, 2)
        self.assertEqual(self.conf.first_viewed_at, first)


# ─────────────────────────── set_decision ───────────────────────────

class SetDecisionTests(TestCase):
    def setUp(self):
        self.client_user, self.party = _make_client_with_party("sd_cli", "طرف‌حساب تصمیم")
        self.project = _make_project(self.party)
        self.stage = _make_stage(self.project, kind=StageKind.SHIPPING, status=ProjectStage.Status.DONE)
        self.conf = StageConfirmation.objects.create(stage=self.stage, recipient=self.client_user)

    def test_valid_decision_received(self):
        result = set_decision(
            stage_id=self.stage.pk,
            decision=StageConfirmation.Decision.RECEIVED,
            actor=self.client_user,
        )
        self.assertEqual(result.decision, StageConfirmation.Decision.RECEIVED)
        self.assertIsNotNone(result.decided_at)
        self.assertEqual(result.decided_by, self.client_user)

    def test_valid_decision_not_received(self):
        result = set_decision(
            stage_id=self.stage.pk,
            decision=StageConfirmation.Decision.NOT_RECEIVED,
            actor=self.client_user,
        )
        self.assertEqual(result.decision, StageConfirmation.Decision.NOT_RECEIVED)

    def test_idempotent_same_decision_no_change(self):
        set_decision(stage_id=self.stage.pk, decision=StageConfirmation.Decision.RECEIVED, actor=self.client_user)
        self.conf.refresh_from_db()
        first_decided_at = self.conf.decided_at
        set_decision(stage_id=self.stage.pk, decision=StageConfirmation.Decision.RECEIVED, actor=self.client_user)
        self.conf.refresh_from_db()
        self.assertEqual(self.conf.decided_at, first_decided_at)

    def test_invalid_decision_for_kind_raises(self):
        with self.assertRaises(ValueError):
            set_decision(
                stage_id=self.stage.pk,
                decision=StageConfirmation.Decision.CONFIRMED,   # برای SHIPPING معتبر نیست
                actor=self.client_user,
            )

    def test_non_recipient_raises(self):
        other_party = Party.objects.create(name="دیگری", is_client=True)
        other_user = User.objects.create_user(
            username="sd_other", password="pw", role=User.Role.CLIENT, party=other_party
        )
        with self.assertRaises(ValueError):
            set_decision(
                stage_id=self.stage.pk,
                decision=StageConfirmation.Decision.RECEIVED,
                actor=other_user,
            )

    def test_nonexistent_stage_raises(self):
        with self.assertRaises(ValueError):
            set_decision(stage_id=99999, decision=StageConfirmation.Decision.RECEIVED, actor=self.client_user)

    def test_cancelled_project_raises(self):
        self.project.status = Project.Status.CANCELLED
        self.project.save(update_fields=["status"])
        with self.assertRaises(ValueError):
            set_decision(
                stage_id=self.stage.pk,
                decision=StageConfirmation.Decision.RECEIVED,
                actor=self.client_user,
            )

    def test_install_confirmed_decision(self):
        install_stage = _make_stage(self.project, kind=StageKind.INSTALL, status=ProjectStage.Status.DONE)
        StageConfirmation.objects.create(stage=install_stage, recipient=self.client_user)
        result = set_decision(
            stage_id=install_stage.pk,
            decision=StageConfirmation.Decision.CONFIRMED,
            actor=self.client_user,
        )
        self.assertEqual(result.decision, StageConfirmation.Decision.CONFIRMED)


# ─────────────────────────── variant property ───────────────────────────

class StageConfirmationVariantTests(TestCase):
    def setUp(self):
        _, party = _make_client_with_party("var_cli", "طرف‌حساب variant")
        project = _make_project(party)
        stage = _make_stage(project, kind=StageKind.SHIPPING)
        self.conf = StageConfirmation.objects.create(stage=stage)

    def test_pending_variant(self):
        self.conf.decision = StageConfirmation.Decision.PENDING
        self.assertEqual(self.conf.variant, "warning")

    def test_received_variant(self):
        self.conf.decision = StageConfirmation.Decision.RECEIVED
        self.assertEqual(self.conf.variant, "success")

    def test_not_received_variant(self):
        self.conf.decision = StageConfirmation.Decision.NOT_RECEIVED
        self.assertEqual(self.conf.variant, "error")

    def test_confirmed_variant(self):
        self.conf.decision = StageConfirmation.Decision.CONFIRMED
        self.assertEqual(self.conf.variant, "success")


# ─────────────────────────── shipped_services & install_images ───────────────────────────

class ShippedServicesAndInstallImagesTests(TestCase):
    def setUp(self):
        _, party = _make_client_with_party("ss_cli", "طرف‌حساب خدمات")
        self.project = _make_project(party)
        self.stage = _make_stage(self.project, kind=StageKind.INSTALL)

    def test_shipped_services_empty_project(self):
        self.assertEqual(shipped_services(self.project), [])

    def test_shipped_services_returns_name_and_qty(self):
        srv = Service.objects.create(name="نصب داکت اسپلیت", code="SRV-1", unit="piece")
        ProjectService.objects.create(project=self.project, service=srv, qty=2, unit_price=1000)
        items = shipped_services(self.project)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "نصب داکت اسپلیت")
        self.assertEqual(items[0]["qty"], 2)
        self.assertEqual(items[0]["unit"], "عدد")

    def test_install_images_filters_only_images(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f_img = SimpleUploadedFile("install.jpg", b"fake image content", content_type="image/jpeg")
        f_pdf = SimpleUploadedFile("doc.pdf", b"fake pdf content", content_type="application/pdf")
        pf_img = ProjectFile.objects.create(stage=self.stage, file=f_img, kind=ProjectFile.Kind.IMAGE, is_attachment=True)
        ProjectFile.objects.create(stage=self.stage, file=f_pdf, kind=ProjectFile.Kind.OTHER, is_attachment=True)
        images = install_images(self.stage)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].pk, pf_img.pk)


# ─────────────────────────── complete_stage integration ───────────────────────────

class CompleteStageConfirmationIntegrationTests(TestCase):
    def setUp(self):
        call_command("setup_notification_policies", stdout=StringIO())
        self.manager = _make_manager("cs_mgr")
        self.client_user, self.party = _make_client_with_party("cs_cli", "مشتری تکمیل مرحله")
        self.project = _make_project(self.party)

    def test_complete_shipping_stage_triggers_open_confirmation(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        stage = _make_stage(self.project, kind=StageKind.SHIPPING, status=ProjectStage.Status.IN_PROGRESS)
        stage.assigned_to = self.manager
        stage.save()
        # ارسال نیاز به تصویر دارد
        f_img = SimpleUploadedFile("shipped.png", b"img", content_type="image/png")
        ProjectFile.objects.create(stage=stage, file=f_img, kind=ProjectFile.Kind.IMAGE, is_attachment=True)

        with mock.patch("notifications.services.SMSService.send_shipment_sent", return_value={"success": True, "message_id": 1}):
            with self.captureOnCommitCallbacks(execute=True):
                result = complete_stage(stage=stage, actor=self.manager, comment="ارسال شد")
        self.assertEqual(result.status, ProjectStage.Status.DONE)
        self.assertTrue(StageConfirmation.objects.filter(stage=result).exists())
        conf = StageConfirmation.objects.get(stage=result)
        self.assertEqual(conf.recipient, self.client_user)
        self.assertEqual(conf.decision, StageConfirmation.Decision.PENDING)

