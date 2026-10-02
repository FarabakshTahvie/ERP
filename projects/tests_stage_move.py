from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from projects.models import ProjectStage, StageKind, StageEvent
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake, advance_stage
from projects.stage_move import move_to_stage


class StageMoveReturnModeTests(TestCase):
    """پوشش گزینه‌ی انتخابی رفتار بازگشتی هنگام انتقال مرحله."""

    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست انتقال", is_partner=True, phone_number="09121119900")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.creator = User.objects.create_user(username="mv_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )
        stage1 = self.project.stages.get(order=1)
        stage1.assigned_to = self.creator
        stage1.save()
        advance_stage(stage1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید انجام شد.")
        # الان مرحله‌ی فعلی: صدور پیش‌فاکتور (order=2)

    def test_return_mode_default_brings_project_back_to_origin(self):
        assembly = self.project.stages.get(title="مونتاژ")
        origin = self.project.stages.get(order=2)
        self.assertEqual(origin.status, ProjectStage.Status.IN_PROGRESS)

        target = move_to_stage(project=self.project, target_id=assembly.id, actor=self.creator,
                               comment="باید زودتر مونتاژ انجام شود", return_to_current=True)
        self.assertEqual(target.id, assembly.id)
        self.assertEqual(target.return_to_id, origin.id)

        origin.refresh_from_db()
        self.assertEqual(origin.status, ProjectStage.Status.PENDING)

        advance_stage(target, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="مونتاژ تمام شد.")

        origin.refresh_from_db()
        self.assertEqual(origin.status, ProjectStage.Status.IN_PROGRESS)

    def test_continue_mode_does_not_return_to_origin(self):
        assembly = self.project.stages.get(title="مونتاژ")
        origin = self.project.stages.get(order=2)

        target = move_to_stage(project=self.project, target_id=assembly.id, actor=self.creator,
                               comment="دیگه لازم نیست برگردیم", return_to_current=False)
        self.assertIsNone(target.return_to_id)

        origin.refresh_from_db()
        self.assertEqual(origin.status, ProjectStage.Status.PENDING)

        advance_stage(target, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="مونتاژ تمام شد.")

        origin.refresh_from_db()
        self.assertEqual(origin.status, ProjectStage.Status.PENDING)   # رها شده؛ به آن برنگشتیم

        next_stage = self.project.stages.get(order=assembly.order + 1)
        self.assertEqual(next_stage.status, ProjectStage.Status.IN_PROGRESS)

    def test_view_default_mode_is_return_when_param_missing(self):
        assembly = self.project.stages.get(title="مونتاژ")
        origin = self.project.stages.get(order=2)
        client = Client()
        client.force_login(self.creator)
        client.post(reverse("projects:move_stage", args=[self.project.id]), {
            "target": assembly.id, "comment": "تست پیش‌فرض ویو",
        })
        assembly.refresh_from_db()
        self.assertEqual(assembly.return_to_id, origin.id)

    def test_view_continue_mode_sets_return_to_none(self):
        assembly = self.project.stages.get(title="مونتاژ")
        client = Client()
        client.force_login(self.creator)
        client.post(reverse("projects:move_stage", args=[self.project.id]), {
            "target": assembly.id, "comment": "تست حالت ادامه", "return_mode": "continue",
        })
        assembly.refresh_from_db()
        self.assertIsNone(assembly.return_to_id)

    def test_event_comment_records_chosen_mode(self):
        assembly = self.project.stages.get(title="مونتاژ")
        move_to_stage(project=self.project, target_id=assembly.id, actor=self.creator,
                     comment="یادداشت تست", return_to_current=False)
        event = StageEvent.objects.filter(stage=assembly).order_by("-created_at").first()
        self.assertIn("بدون برگشت", event.comment)

    def test_dialog_has_both_radio_options(self):
        client = Client()
        client.force_login(self.creator)
        resp = client.get(reverse("projects:staff_project_overview", args=[self.project.id]))
        content = resp.content.decode("utf-8")
        self.assertIn('value="return"', content)
        self.assertIn('value="continue"', content)
        self.assertIn('name="return_mode"', content)
