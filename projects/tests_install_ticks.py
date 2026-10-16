import shutil
import tempfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import Service
from core.models import Party
from projects import ops
from projects.models import ProjectService, ProjectStage, ServiceTick, StageKind
from projects.services import create_project_from_technician_intake, transfer_stage
from projects.stage_ops import add_stage_file, complete_stage, stage_completion_problem
from projects.usage import install_context, set_service_done, stage_has_progress
from projects.workflow_v3 import build_workflow_v3
from utils.test_helpers import make_image_file


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class InstallBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        self.partner = Party.objects.create(name="شریک نصب", is_partner=True, phone_number="09125550505")
        mk = User.objects.create_user
        self.creator = mk(username="it_creator", password="pw", role=User.Role.EMPLOYEE)
        self.installer = mk(username="it_installer", password="pw", role=User.Role.EMPLOYEE)
        self.peer = mk(username="it_peer", password="pw", role=User.Role.EMPLOYEE)
        self.stranger = mk(username="it_stranger", password="pw", role=User.Role.EMPLOYEE)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.s1 = ProjectService.objects.create(project=self.project, service=Service.objects.create(name="نصب کانال"),
                                                qty=2, unit_price=1000)
        self.s2 = ProjectService.objects.create(project=self.project, service=Service.objects.create(name="نصب دریچه"),
                                                qty=5, unit_price=500)
        self.stage = self.project.stages.get(kind=StageKind.INSTALL)
        self.stage.status = ProjectStage.Status.IN_PROGRESS
        self.stage.assigned_to = self.installer
        self.stage.save()
        self.client.force_login(self.installer)

    def tick(self, line, done=True, actor=None):
        return set_service_done(stage=self.stage, service_line_id=line.id, done=done, actor=actor or self.installer)


class InstallTickTests(InstallBase):
    def test_tick_is_explicit_idempotent_and_counts(self):
        self.assertEqual(self.tick(self.s1), {"done": 1, "total": 2})
        self.assertEqual(self.tick(self.s1), {"done": 1, "total": 2})
        self.assertEqual(ServiceTick.objects.count(), 1)
        self.assertEqual(self.tick(self.s2), {"done": 2, "total": 2})
        self.assertEqual(self.tick(self.s1, done=False), {"done": 1, "total": 2})
        self.assertEqual(self.tick(self.s1, done=False), {"done": 1, "total": 2})

    def test_permissions_and_validation(self):
        with self.assertRaises(ValueError):
            self.tick(self.s1, actor=self.stranger)
        other, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=date(2026, 10, 12), issue_proforma=False)
        foreign = ProjectService.objects.create(project=other, service=self.s1.service, qty=1, unit_price=1)
        for bad in (foreign.id, "abc", "", None, 999999):
            with self.assertRaises(ValueError, msg=str(bad)):
                set_service_done(stage=self.stage, service_line_id=bad, done=True, actor=self.installer)
        cutting = self.project.stages.get(kind=StageKind.CUTTING)
        with self.assertRaises(ValueError):
            set_service_done(stage=cutting, service_line_id=self.s1.id, done=True, actor=self.installer)
        self.assertFalse(ServiceTick.objects.exists())

    def test_done_stage_is_editable_by_creator_not_by_installer(self):
        ProjectStage.objects.filter(pk=self.stage.pk).update(status=ProjectStage.Status.DONE)
        with self.assertRaises(ValueError):
            self.tick(self.s1)
        self.tick(self.s1, actor=self.creator)
        self.assertEqual(ServiceTick.objects.count(), 1)





class InstallLockTests(InstallBase):
    def test_first_tick_locks_transfer_and_untick_unlocks(self):
        self.peer.specialties.add(self.stage.step_template.responsible_specialty)
        self.assertFalse(stage_has_progress(self.stage))
        self.tick(self.s1)
        self.assertTrue(stage_has_progress(self.stage))
        with self.assertRaises(ValueError):
            transfer_stage(self.stage, from_user=self.installer, to_user=self.peer, comment="")
        self.tick(self.s1, done=False)
        transfer_stage(self.stage, from_user=self.installer, to_user=self.peer, comment="")
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to_id, self.peer.id)


class InstallCompletionTests(InstallBase):
    def test_completion_needs_photo_but_not_every_tick(self):
        self.assertIn("عکس", stage_completion_problem(self.stage))
        add_stage_file(stage=self.stage, uploaded=make_image_file("site.jpg"), uploader=self.installer)
        self.assertIsNone(stage_completion_problem(self.stage))
        complete_stage(stage=self.stage, actor=self.installer, comment="نصب شد")
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.status, ProjectStage.Status.DONE)
        self.assertEqual(ServiceTick.objects.count(), 0)



