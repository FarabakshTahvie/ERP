import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from core.models import Party
from projects.models import ProjectStage, StageEvent
from projects.services import create_project_from_technician_intake
from projects.stage_ops import complete_stage, prepare_voice
from projects.workflow_v3 import build_workflow_v3

WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 2048
M4A = b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 2048
PEAKS = ",".join(str(10 + i) for i in range(32))


def voice(data=WEBM, name="v.webm"):
    return SimpleUploadedFile(name, data, content_type="audio/webm")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class StageVoiceTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        partner = Party.objects.create(name="شریک صدا", is_partner=True, phone_number="09125550202")
        self.tech = User.objects.create_user(username="vo_tech", password="pw", role=User.Role.EMPLOYEE)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.stage = self.project.stages.get(order=1)
        self.stage.assigned_to = self.tech
        self.stage.save()
        self.url = reverse("projects:my_task_complete", args=[self.stage.id])

    def last_event(self):
        return StageEvent.objects.filter(stage=self.stage).order_by("-created_at", "-id").first()

    def test_voice_only_completes_with_default_comment(self):
        v = prepare_voice(voice(), "42", PEAKS)
        complete_stage(stage=self.stage, actor=self.tech, comment="", voice=v)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.DONE)
        ev = self.last_event()
        self.assertEqual((ev.comment, ev.voice_duration, ev.voice_peaks), ("پیام صوتی", 42, PEAKS))
        self.assertTrue(ev.voice.name.startswith(f"projects/{self.project.id}/voice/"))
        self.assertTrue(ev.voice.name.endswith(".webm"))



    def test_neither_text_nor_voice_is_rejected(self):
        with self.assertRaises(ValueError):
            complete_stage(stage=self.stage, actor=self.tech, comment="  ")
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.IN_PROGRESS)

    def test_extension_comes_from_real_format_and_fake_is_rejected(self):
        self.assertTrue(prepare_voice(voice(M4A, "x.mp3"), "10", PEAKS)["voice"].name.endswith(".m4a"))
        with self.assertRaises(ValueError):
            prepare_voice(voice(b"not audio at all", "v.webm"), "10", PEAKS)



    def test_size_limit(self):
        with self.assertRaises(ValueError):
            prepare_voice(voice(WEBM + b"\x00" * (12 * 1024 * 1024)), "10", PEAKS)



    def test_view_rejects_fake_voice_and_keeps_stage_open(self):
        self.client.force_login(self.tech)
        self.client.post(self.url, {"comment": "", "voice": voice(b"junk junk junk junk"), "voice_duration": "30"})
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.IN_PROGRESS)


