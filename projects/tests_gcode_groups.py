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
from projects.models import FileGroup, ProjectFile, ProjectStage, StageKind
from projects.services import create_project_from_technician_intake
from projects.stage_ops import (
    add_stage_file, create_group, cut_groups, groups_progress, set_group_cut_done, stage_completion_problem,
)
from projects.workflow_v3 import build_workflow_v3


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GroupBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        partner = Party.objects.create(name="شریک گروه", is_partner=True, phone_number="09125550303")
        self.tech = User.objects.create_user(username="gg_tech", password="pw", role=User.Role.EMPLOYEE)
        self.other = User.objects.create_user(username="gg_other", password="pw", role=User.Role.EMPLOYEE)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.gcode = self.open_stage(StageKind.GCODE)
        self.cutting = self.open_stage(StageKind.CUTTING)

    def open_stage(self, kind):
        stage = self.project.stages.get(kind=kind)
        stage.status = ProjectStage.Status.IN_PROGRESS
        stage.assigned_to = self.tech
        stage.save()
        return stage

    def group(self, title="طبقه اول"):
        return create_group(stage=self.gcode, title=title, actor=self.tech)

    def upload(self, group, name="a.nc", cuts="3"):
        return add_stage_file(stage=self.gcode, uploaded=SimpleUploadedFile(name, b"gcode"),
                              uploader=self.tech, cut_count_raw=cuts, group_id=group.id)


class GroupCreateTests(GroupBase):
    def test_title_is_normalized_and_duplicates_rejected(self):
        self.assertEqual(self.group("  طبقه   اول ").title, "طبقه اول")
        with self.assertRaises(ValueError):
            self.group("طبقه اول")
        self.group("طبقه ۲")
        with self.assertRaises(ValueError):
            self.group("طبقه 2")

    def test_bad_titles_actors_and_stages(self):
        for bad in ("", "   ", "ا" * 101):
            with self.assertRaises(ValueError, msg=bad):
                create_group(stage=self.gcode, title=bad, actor=self.tech)
        with self.assertRaises(ValueError):
            create_group(stage=self.gcode, title="x", actor=self.other)
        with self.assertRaises(ValueError):
            create_group(stage=self.cutting, title="x", actor=self.tech)
        ProjectStage.objects.filter(pk=self.gcode.pk).update(status=ProjectStage.Status.DONE)
        with self.assertRaises(ValueError):
            create_group(stage=self.gcode, title="y", actor=self.tech)


class GroupUploadTests(GroupBase):
    def test_gcode_upload_needs_group_of_this_stage_and_cut_count(self):
        g = self.group()
        foreign = FileGroup.objects.create(project=self.project, stage=self.cutting, title="بیگانه")
        for gid in (None, "", "abc", "999999", foreign.id):
            with self.assertRaises(ValueError, msg=str(gid)):
                add_stage_file(stage=self.gcode, uploaded=SimpleUploadedFile("a.nc", b"x"), uploader=self.tech,
                               cut_count_raw="2", group_id=gid)
        with self.assertRaises(ValueError):
            add_stage_file(stage=self.gcode, uploaded=SimpleUploadedFile("a.nc", b"x"), uploader=self.tech,
                               cut_count_raw="", group_id=g.id)
        f = self.upload(g)
        self.assertEqual((f.group_id, f.cut_count), (g.id, 3))

    def test_new_file_reopens_a_done_group(self):
        g = self.group()
        self.upload(g)
        set_group_cut_done(group=g, done=True, actor=self.tech)
        self.upload(g, "b.nc", "2")
        g.refresh_from_db()
        self.assertFalse(g.cut_done)
        self.assertIsNone(g.cut_done_by)


class GroupCutTests(GroupBase):
    def test_empty_groups_are_ignored(self):
        g1 = self.group("طبقه اول")
        self.group("طبقه دوم")
        self.upload(g1)
        self.assertEqual([g.id for g in cut_groups(self.project)], [g1.id])
        self.assertEqual(groups_progress(self.project), (1, 0))

    def test_done_and_undone_are_explicit_and_idempotent(self):
        g = self.group()
        self.upload(g)
        set_group_cut_done(group=g, done=True, actor=self.tech)
        set_group_cut_done(group=g, done=True, actor=self.tech)
        g.refresh_from_db()
        self.assertTrue(g.cut_done)
        self.assertEqual(g.cut_done_by, self.tech)
        self.assertIsNotNone(g.cut_done_at)
        self.assertEqual(groups_progress(self.project), (1, 1))
        set_group_cut_done(group=g, done=False, actor=self.tech)
        g.refresh_from_db()
        self.assertFalse(g.cut_done)
        self.assertIsNone(g.cut_done_by)

    def test_group_cut_rules(self):
        g = self.group()
        self.upload(g)
        empty = self.group("خالی")
        with self.assertRaises(ValueError):
            set_group_cut_done(group=g, done=True, actor=self.other)
        with self.assertRaises(ValueError):
            set_group_cut_done(group=empty, done=True, actor=self.tech)
        ProjectStage.objects.filter(pk=self.cutting.pk).update(status=ProjectStage.Status.PENDING)
        with self.assertRaises(ValueError):
            set_group_cut_done(group=g, done=True, actor=self.tech)

    def test_cutting_blocked_until_every_group_is_done(self):
        self.assertIn("گروه", stage_completion_problem(self.cutting))
        g1, g2 = self.group("طبقه اول"), self.group("طبقه دوم")
        self.upload(g1)
        self.upload(g2, "b.nc")
        self.assertIn("2 گروه", stage_completion_problem(self.cutting))
        set_group_cut_done(group=g1, done=True, actor=self.tech)
        self.assertIn("1 گروه از 2 گروه", stage_completion_problem(self.cutting))
        set_group_cut_done(group=g2, done=True, actor=self.tech)
        self.assertIsNone(stage_completion_problem(self.cutting))

    def test_gcode_completion_needs_every_file_grouped(self):
        g = self.group()
        self.upload(g)
        self.assertIsNone(stage_completion_problem(self.gcode))
        ProjectFile.objects.create(stage=self.gcode, file=SimpleUploadedFile("z.nc", b"x"), kind="gcode",
                                   original_name="z.nc", is_attachment=True, cut_count=2)
        self.assertIn("گروه", stage_completion_problem(self.gcode))



