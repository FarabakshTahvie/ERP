import json
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item, MarginRule
from inventory.models import Warehouse, StockMovement
from inventory.services import receive_stock
from projects.models import (
    Project, ProjectStage, StageKind, ProjectFile,
    ProjectCost, StageEvent,
)
from projects.workflow_v3 import build_workflow_v3
from projects.services import create_project_from_technician_intake, advance_stage
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects.stage_ops import add_stage_file, complete_stage, stage_completion_problem
from projects.ops import add_project_cost, delete_project_cost


class ProjectCostAndReviewTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک ۵", is_partner=True, phone_number="09121112277")
        self.intake_spec = Specialty.objects.get_or_create(name="پذیرش")[0]
        self.creator = User.objects.create_user(username="creator_rev", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.intake_spec)
        self.acc_spec = Specialty.objects.get_or_create(name="حسابدار")[0]
        self.accountant = User.objects.create_user(username="acc_rev", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.acc_spec)
        self.other_user = User.objects.create_user(username="other_rev", password="pw", role=User.Role.EMPLOYEE)

        build_workflow_v3(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(created_by=self.creator, party_id=self.partner.id, visit_at=timezone.now(), issue_proforma=False)

    def test_complete_stage_final_review_requires_via_review(self):
        rev_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        rev_stage.status = ProjectStage.Status.IN_PROGRESS
        rev_stage.assigned_to = self.creator
        rev_stage.save()
        with self.assertRaises(ValueError) as cm:
            complete_stage(stage=rev_stage, actor=self.creator, comment="تکمیل بدون بازبینی", via_review=False)
        self.assertIn("بازبینی نهایی فقط از صفحه‌ی «بازبینی نهایی» تایید می‌شود", str(cm.exception))

    def test_cost_addition_and_deletion(self):
        with self.assertRaises(ValueError):
            add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="-1000", actor=self.accountant)

        # creator cannot add cost
        with self.assertRaises(ValueError):
            add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="15000", actor=self.creator)

        cost = add_project_cost(project=self.project, kind="other", title="هزینه ۱", amount_raw="15000", actor=self.accountant)
        self.assertEqual(self.project.recorded_costs.count(), 1)
        self.assertEqual(cost.amount, Decimal("15000"))

        with self.assertRaises(ValueError):
            delete_project_cost(cost=cost, actor=self.other_user)

        with self.assertRaises(ValueError):
            delete_project_cost(cost=cost, actor=self.creator)

        delete_project_cost(cost=cost, actor=self.accountant)
        self.assertEqual(self.project.recorded_costs.count(), 0)
