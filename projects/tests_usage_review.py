from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, Service
from core.models import Party, Specialty
from finance import accounting
from inventory.models import StockMovement, Warehouse
from inventory.services import receive_stock
from projects.models import Project, ProjectService, ProjectServiceMaterial, ProjectStage, StageKind, StageUsage
from projects.services import create_project_from_technician_intake
from projects.usage import project_usage_by_stage
from projects.workflow_v3 import build_workflow_v3


class ReviewBase(TestCase):
    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        partner = Party.objects.create(name="شریک بازبینی", is_partner=True, phone_number="09125550606")
        mk = User.objects.create_user
        self.creator = mk(username="rv_creator", password="pw", role=User.Role.EMPLOYEE)
        self.accountant = mk(username="rv_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        self.manager = mk(username="rv_mgr", password="pw", role=User.Role.ADMIN)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.item = Item.objects.create(name="ورق گالوانیزه", item_type=Item.ItemType.MATERIAL,
                                        unit=Item.Unit.SQUARE_METER)
        self.other = Item.objects.create(name="پیچ", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        line = ProjectService.objects.create(project=self.project, service=Service.objects.create(name="خدمت بازبینی"),
                                             qty=1, unit_price=1000)
        ProjectServiceMaterial.objects.create(service_line=line, item=self.item, qty=Decimal("10"))
        self.cutting = self.project.stages.get(kind=StageKind.CUTTING)
        self.assembly = self.project.stages.get(kind=StageKind.ASSEMBLY)
        self.final = self.project.stages.get(kind=StageKind.FINAL_REVIEW)

    def use(self, stage, item, qty, by=None):
        return StageUsage.objects.create(stage=stage, item=item, qty=Decimal(qty), updated_by=by)

    def open_final(self):
        ProjectStage.objects.filter(pk=self.final.pk).update(status=ProjectStage.Status.IN_PROGRESS)


class UsageByStageTests(ReviewBase):
    def test_empty_project(self):
        self.assertEqual(project_usage_by_stage(self.project), [])

    def test_only_used_stages_in_stage_order_with_extra_flag(self):
        self.use(self.assembly, self.item, "2", self.creator)
        self.use(self.cutting, self.other, "7")
        self.use(self.cutting, self.item, "4.5", self.creator)
        groups = project_usage_by_stage(self.project)
        self.assertEqual([g["stage"].pk for g in groups], [self.cutting.pk, self.assembly.pk])
        self.assertEqual({(r["item"].pk, r["qty"], r["extra"]) for r in groups[0]["rows"]},
                         {(self.other.pk, Decimal("7"), True), (self.item.pk, Decimal("4.5"), False)})
        self.assertEqual(groups[1]["rows"][0]["by"], self.creator)

    def test_total_equals_reconciliation_used(self):
        self.use(self.cutting, self.item, "4.5")
        self.use(self.assembly, self.item, "2")
        total = sum(r["qty"] for g in project_usage_by_stage(self.project) for r in g["rows"]
                    if r["item"].pk == self.item.pk)
        recon = next(r for r in accounting.project_reconciliation(self.project) if r["item"].pk == self.item.pk)
        self.assertEqual((total, recon["used"]), (Decimal("6.5"), Decimal("6.5")))


class ReconciliationExtrasTests(ReviewBase):
    def test_unit_label_and_stock_hint(self):
        wh = Warehouse.objects.create(name="انبار بازبینی", is_default=True)
        receive_stock(item=self.item, warehouse=wh, qty=Decimal("5"), unit_cost=Decimal("100"),
                      received_at=timezone.now())
        self.use(self.cutting, self.item, "8")
        r = accounting.project_reconciliation(self.project)[0]
        self.assertEqual(r["unit_label"], "متر مربع")
        self.assertEqual((r["stock"], r["unsettled"], r["stock_short"]), (Decimal("5"), Decimal("8"), True))
        receive_stock(item=self.item, warehouse=wh, qty=Decimal("10"), unit_cost=Decimal("100"),
                      received_at=timezone.now())
        self.assertFalse(accounting.project_reconciliation(self.project)[0]["stock_short"])


class ReviewPageTests(ReviewBase):
    def page(self, user=None):
        c = Client()
        c.force_login(user or self.manager)
        return c.get(reverse("projects:final_review", args=[self.project.id]))

    def test_empty_state(self):
        self.assertContains(self.page(), "هیچ مرحله‌ای مصرف ثبت نکرده است.")

    def test_unassigned_stage_and_unknown_recorder_render_dash(self):
        self.use(self.cutting, self.item, "3")          # بدون ثبت‌کننده؛ مرحله هم مسئول ندارد
        self.assertIsNone(self.cutting.assigned_to_id)
        resp = self.page()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "مسئول: —")

    def test_sections_and_context(self):
        self.open_final()
        self.use(self.cutting, self.item, "4.5", self.creator)
        self.use(self.assembly, self.item, "2")
        resp = self.page()
        self.assertContains(resp, "مصرف ثبت‌شده‌ی هر مرحله")
        self.assertContains(resp, "جمع مصرف همه‌ی مراحل و تسویه‌ی انبار")
        self.assertContains(resp, "موجودی انبار")
        self.assertContains(resp, "data-decimal data-settle-qty")
        self.assertEqual([g["stage"].pk for g in resp.context["usage_stages"]], [self.cutting.pk, self.assembly.pk])

    def test_accounting_project_page_shows_section(self):
        self.use(self.cutting, self.item, "4")
        c = Client()
        c.force_login(self.manager)
        resp = c.get(reverse("finance:accounting_project", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "مصرف ثبت‌شده‌ی هر مرحله")


class ReviewSettlementTests(ReviewBase):
    def setUp(self):
        super().setUp()
        wh = Warehouse.objects.create(name="انبار تسویه", is_default=True)
        receive_stock(item=self.item, warehouse=wh, qty=Decimal("20"), unit_cost=Decimal("100"),
                      received_at=timezone.now())
        self.use(self.cutting, self.item, "4.5")
        self.use(self.assembly, self.item, "2")

    def out_total(self):
        ct = ContentType.objects.get_for_model(Project)
        return (StockMovement.objects.filter(related_content_type=ct, related_object_id=self.project.pk,
                                             direction=StockMovement.Direction.OUT)
                .aggregate(t=Sum("qty"))["t"] or Decimal("0"))

    def test_default_settlement_deducts_the_sum_of_all_stages(self):
        accounting.settle_project_materials(project=self.project, final_qtys={}, reasons={}, actor=self.accountant)
        self.assertEqual(self.out_total(), Decimal("6.5"))

    def test_accountant_can_change_with_reason_only(self):
        with self.assertRaises(ValueError):
            accounting.settle_project_materials(project=self.project, final_qtys={self.item.pk: Decimal("7")},
                                                reasons={}, actor=self.accountant)
        self.assertEqual(self.out_total(), Decimal("0"))
        accounting.settle_project_materials(project=self.project, final_qtys={self.item.pk: Decimal("7")},
                                            reasons={self.item.pk: "ضایعات"}, actor=self.accountant)
        self.assertEqual(self.out_total(), Decimal("7"))

    def test_review_post_settles_decimal_total(self):
        self.open_final()
        c = Client()
        c.force_login(self.accountant)
        resp = c.post(reverse("projects:final_review", args=[self.project.id]),
                      {"comment": "تایید نهایی", f"final_qty_{self.item.id}": "6.5"})
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETED)
        self.assertEqual(self.out_total(), Decimal("6.5"))


class ReviewTemplateTextTests(TestCase):
    def test_decimal_inputs_and_updated_copy(self):
        text = (Path(settings.BASE_DIR) / "templates" / "projects" / "final_review.html").read_text(encoding="utf-8")
        self.assertRegex(text, r'<input[^>]*id="fr-stock-qty"[^>]*data-decimal')
        self.assertIn("data-decimal data-settle-qty", text)
        self.assertIn("usage_by_stage.html", text)
        self.assertNotIn("درخواست قطعه", text)
        self.assertNotIn("اضافه‌ی ارسالی", text)
