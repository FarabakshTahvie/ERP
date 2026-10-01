from decimal import Decimal
from datetime import date
from unittest import mock
import jdatetime
from django.test import TestCase
from accounts.models import User
from core.models import Party, Specialty
from projects.models import (
    Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate,
    ProjectFile, StageKind, StageApproval,
)
from projects.workflow_v2 import build_workflow_v2, TEMPLATE_NAME
from projects.services import (
    create_project_from_technician_intake,
    _assign_stage_responsible,
    update_visit_at,
    can_edit_project,
)
from utils.utils import next_monthly_code, monthly_prefix


class MonthlyCodeTests(TestCase):
    def setUp(self):
        self.party = Party.objects.create(name="شریک", is_partner=True, national_code="1111111111")

    def test_next_code_is_numeric_not_string_order(self):
        for code in ("P0507-01", "P0507-09", "P0507-10", "P0507-99", "P0507-100", "P0508-05", "P0507-abc"):
            Project.objects.create(name=code, partner=self.party, code=code)
        self.assertEqual(next_monthly_code(Project.objects.all(), "code", "P0507-"), "P0507-101")
        self.assertEqual(next_monthly_code(Project.objects.all(), "code", "P0509-"), "P0509-01")

    def test_code_resets_each_jalali_month(self):
        with mock.patch("utils.utils.timezone.localdate", return_value=date(2026, 9, 30)):    # ۱۴۰۵/۰۷/۰۸
            a = Project.objects.create(name="a", partner=self.party)
            b = Project.objects.create(name="b", partner=self.party)
        with mock.patch("utils.utils.timezone.localdate", return_value=date(2026, 10, 25)):   # ۱۴۰۵/۰۸/۰۳
            c = Project.objects.create(name="c", partner=self.party)
        self.assertEqual((a.code, b.code, c.code), ("P0507-01", "P0507-02", "P0508-01"))

    def test_retry_on_duplicate_code(self):
        with mock.patch.object(Project, "_generate_code", side_effect=["P0507-01", "P0507-01", "P0507-02"]):
            p1 = Project.objects.create(name="p1", partner=self.party)
            p2 = Project.objects.create(name="p2", partner=self.party)
            self.assertEqual(p1.code, "P0507-01")
            self.assertEqual(p2.code, "P0507-02")


class WorkflowV2Tests(TestCase):
    def setUp(self):
        self.internal = Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        self.partner = Party.objects.create(name="شریک آزمایشی", is_partner=True, phone_number="09120000001")
        self.intake_spec = Specialty.objects.create(name="پذیرش")
        self.tech = User.objects.create_user(username="tech1", password="pw", role=User.Role.EMPLOYEE)
        self.tech.specialties.add(self.intake_spec)

    def test_build_workflow_v2_idempotent(self):
        tmpl1, created1 = build_workflow_v2(make_default=True)
        self.assertTrue(created1)
        self.assertEqual(tmpl1.steps.count(), 12)
        self.assertTrue(tmpl1.is_default)

        tmpl2, created2 = build_workflow_v2(make_default=True)
        self.assertFalse(created2)
        self.assertEqual(tmpl2.steps.count(), 12)

        steps = list(tmpl1.steps.order_by("order"))
        self.assertEqual(steps[0].kind, StageKind.VISIT)
        self.assertEqual(steps[1].kind, StageKind.PROFORMA)
        self.assertEqual(steps[4].on_reject_go_to, steps[3])

    def test_make_default_unsets_other_templates(self):
        other = WorkflowTemplate.objects.create(name="دیگر", is_default=True)
        v2, _ = build_workflow_v2(make_default=True)
        other.refresh_from_db()
        self.assertFalse(other.is_default)
        self.assertTrue(v2.is_default)

    def test_assign_stage_responsible_order(self):
        spec = Specialty.objects.create(name="تست تخصص")
        emp1 = User.objects.create_user(username="emp1", password="pw", role=User.Role.EMPLOYEE)
        emp1.specialties.add(spec)
        default_user = User.objects.create_user(username="default_u", password="pw", role=User.Role.EMPLOYEE)

        tmpl = WorkflowTemplate.objects.create(name="تست ارجاع")
        step_template = WorkflowStepTemplate.objects.create(
            template=tmpl, order=1, title="مرحله ۱",
            default_assignee=default_user,
            assign_to_project_creator=True,
            responsible_specialty=spec,
        )
        p = Project.objects.create(name="پروژه", partner=self.partner, created_by=self.tech)
        stage = ProjectStage.objects.create(project=p, step_template=step_template, order=1, title="مرحله")

        # 1. Default assignee wins
        _assign_stage_responsible(stage)
        self.assertEqual(stage.assigned_to, default_user)

        # 2. Project creator wins when no default assignee
        step_template.default_assignee = None
        step_template.save()
        stage.assigned_to = None
        _assign_stage_responsible(stage)
        self.assertEqual(stage.assigned_to, self.tech)

        # 3. Specialty candidates when no creator assignment
        step_template.assign_to_project_creator = False
        step_template.save()
        stage.assigned_to = None
        candidates = _assign_stage_responsible(stage)
        self.assertIn(emp1, candidates)
        self.assertTrue(stage.candidate_users.filter(pk=emp1.pk).exists())

    def test_new_intake_workflow_v2(self):
        build_workflow_v2(make_default=True)
        visit_time = timezone_now = jdatetime.datetime.now()
        from django.utils import timezone
        now_dt = timezone.now()

        from django.core.files.uploadedfile import SimpleUploadedFile
        f1 = SimpleUploadedFile("map1.dwg", b"dwg content 1")
        f2 = SimpleUploadedFile("map2.dwg", b"dwg content 2")
        f3 = SimpleUploadedFile("map3.dwg", b"dwg content 3")

        project, invoice, conflict = create_project_from_technician_intake(
            created_by=self.tech,
            party_id=self.partner.id,
            visit_at=now_dt,
            uploaded_files=[f1, f2, f3],
            issue_proforma=False,
        )
        self.assertIsNone(invoice)
        self.assertFalse(conflict)
        self.assertEqual(project.visit_at, now_dt)

        stages = project.stages.order_by("order")
        first_stage = stages[0]
        self.assertEqual(first_stage.status, ProjectStage.Status.IN_PROGRESS)
        self.assertIsNone(first_stage.assigned_to)
        self.assertEqual(first_stage.kind, StageKind.VISIT)

        # All 3 files are current
        files = list(ProjectFile.objects.filter(stage=first_stage))
        self.assertEqual(len(files), 3)
        self.assertTrue(all(f.is_current for f in files))
        self.assertEqual({f.original_name for f in files}, {"map1.dwg", "map2.dwg", "map3.dwg"})

    def test_new_intake_without_visit_at_fails(self):
        build_workflow_v2(make_default=True)
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=self.tech,
                party_id=self.partner.id,
                visit_at=None,
                issue_proforma=False,
            )

    def test_new_intake_non_v2_template_fails(self):
        WorkflowTemplate.objects.filter(is_default=True).update(is_default=False)
        old_tmpl = WorkflowTemplate.objects.create(name="قالب قدیمی", is_default=True)
        WorkflowStepTemplate.objects.create(template=old_tmpl, order=1, title="قدیمی", kind=StageKind.GENERIC)

        from django.utils import timezone
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=self.tech,
                party_id=self.partner.id,
                visit_at=timezone.now(),
                issue_proforma=False,
            )

    def test_update_visit_at(self):
        build_workflow_v2(make_default=True)
        from django.utils import timezone
        now_dt = timezone.now()
        project, _, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=self.partner.id, visit_at=now_dt, issue_proforma=False,
        )
        new_dt = now_dt + timezone.timedelta(days=2)
        update_visit_at(project=project, actor=self.tech, visit_at=new_dt)
        project.refresh_from_db()
        self.assertEqual(project.visit_at, new_dt)

        # Cannot update after visit stage is DONE
        visit_stage = project.stages.filter(kind=StageKind.VISIT).first()
        visit_stage.status = ProjectStage.Status.DONE
        visit_stage.save()

        with self.assertRaises(ValueError):
            update_visit_at(project=project, actor=self.tech, visit_at=now_dt)
