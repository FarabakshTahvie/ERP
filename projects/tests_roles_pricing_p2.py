from decimal import Decimal
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, Service
from core.models import Party, Specialty
from projects.models import Project, ProjectStage, StageKind, ExtraShipment
from projects.proforma import save_proforma, issue_proforma
from projects.services import create_project_from_technician_intake, advance_stage
from projects.workflow_v2 import build_workflow_v2


class P2RolesTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست نقش‌ها", is_partner=True, phone_number="09123334455")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")

        self.creator = User.objects.create_user(username="tech_intake_r", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)

        self.accountant = User.objects.create_user(username="acc_user_r", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)

        self.manager = User.objects.create_user(username="manager_user_r", password="pw", role=User.Role.ADMIN, is_staff=True)

        self.item = Item.objects.create(name="کالای نقش", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("1000"))
        self.service = Service.objects.create(name="خدمت نقش")

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id,
            visit_date=timezone.localdate(), issue_proforma=False,
        )

    def test_reception_cannot_access_accounting_views_and_actions(self):
        client = Client()
        client.force_login(self.creator)

        # final_review -> 404
        self.assertEqual(client.get(reverse("projects:final_review", args=[self.project.id])).status_code, 404)
        # final_review_consume -> 404
        self.assertEqual(client.post(reverse("projects:final_review_consume", args=[self.project.id]), {
            "item_id": self.item.id, "kind": "consume", "qty": "1", "notes": "تست"
        }).status_code, 404)
        # payments_review -> 302
        self.assertEqual(client.get(reverse("finance:payments_review")).status_code, 302)
        # proforma_editor -> 404
        self.assertEqual(client.get(reverse("projects:proforma_editor", args=[self.project.id])).status_code, 404)
        # save_proforma -> ValueError
        with self.assertRaises(ValueError):
            save_proforma(project=self.project, actor=self.creator, service_rows=[])

    def test_accountant_and_manager_have_full_access(self):
        client = Client()
        for u in (self.accountant, self.manager):
            client.force_login(u)
            self.assertEqual(client.get(reverse("projects:final_review", args=[self.project.id])).status_code, 200)
            self.assertEqual(client.get(reverse("finance:payments_review")).status_code, 200)
            self.assertEqual(client.get(reverse("projects:proforma_editor", args=[self.project.id])).status_code, 200)

    def test_proforma_and_final_review_stages_assigned_to_accountant(self):
        proforma_st = self.project.stages.get(kind=StageKind.PROFORMA)
        self.assertNotEqual(proforma_st.assigned_to, self.creator)
        self.assertEqual(proforma_st.step_template.responsible_specialty.name, "حسابدار")

        final_st = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        self.assertNotEqual(final_st.assigned_to, self.creator)
        self.assertEqual(final_st.step_template.responsible_specialty.name, "حسابدار")


class P2ExtraLinesTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست ردیف اضافه", is_partner=True, phone_number="09127778899")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.accountant = User.objects.create_user(username="acc_extra_l", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.service = Service.objects.create(name="سرویس کانال")

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.accountant, party_id=self.partner.id,
            visit_date=timezone.localdate(), issue_proforma=False,
        )
        st1 = self.project.stages.first()
        advance_stage(st1, actor=self.accountant, new_status=ProjectStage.Status.DONE, comment="بازدید شد")

    def test_save_extra_and_discount_lines(self):
        svc_rows = [{"pk": None, "service_id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("1000000"), "materials": []}]
        extra_rows = [
            {"pk": None, "title": "خسارت قطعه", "kind": "extra", "qty": Decimal("2"), "unit_price": Decimal("50000")},
            {"pk": None, "title": "تخفیف مشتری", "kind": "discount", "qty": Decimal("1"), "unit_price": Decimal("30000")},
        ]
        save_proforma(project=self.project, actor=self.accountant, service_rows=svc_rows, extra_rows=extra_rows)
        invoice, _ = issue_proforma(project=self.project, actor=self.accountant)

        # 1,000,000 + (2 * 50,000) - (1 * 30,000) = 1,070,000
        self.assertEqual(invoice.total_amount, Decimal("1070000"))
        disc_line = invoice.lines.filter(line_type="discount").first()
        self.assertIsNotNone(disc_line)
        self.assertEqual(disc_line.unit_price, Decimal("-30000"))

    def test_total_lte_zero_issue_fails(self):
        svc_rows = [{"pk": None, "service_id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("10000"), "materials": []}]
        extra_rows = [{"pk": None, "title": "تخفیف کامل", "kind": "discount", "qty": Decimal("1"), "unit_price": Decimal("10000")}]
        save_proforma(project=self.project, actor=self.accountant, service_rows=svc_rows, extra_rows=extra_rows)
        with self.assertRaises(ValueError):
            issue_proforma(project=self.project, actor=self.accountant)
