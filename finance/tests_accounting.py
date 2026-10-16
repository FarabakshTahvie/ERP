from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, ItemCategory
from core.models import Party, Specialty
from finance import accounting
from finance.models import Invoice, Payment
from inventory.models import Purchase, PurchaseLine, StockLot, StockMovement, Warehouse
from inventory.services import consume_stock, create_purchase_from_form, receive_stock, record_manual_stock_change
from projects.models import (
    Project, ProjectCost, ProjectService, ProjectServiceMaterial,
    ProjectStage, StageKind, StageUsage, WorkflowStepTemplate, WorkflowTemplate,
)
from projects.services import user_can_access_accounting


class BaseAccountingTestCase(TestCase):
    def setUp(self):
        self.acc_spec, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.wh_spec, _ = Specialty.objects.get_or_create(name="انباردار")

        self.accountant = User.objects.create_user(
            username="acc_user", phone_number="09121111111", role=User.Role.EMPLOYEE, is_staff=True,
        )
        self.accountant.specialties.add(self.acc_spec)

        self.manager = User.objects.create_superuser(
            username="admin_user", phone_number="09122222222", password="password123",
        )

        self.tech = User.objects.create_user(
            username="tech_simple", phone_number="09123333333", role=User.Role.EMPLOYEE,
        )

        self.client_user = User.objects.create_user(
            username="client_user", phone_number="09124444444", role=User.Role.CLIENT,
        )

        self.warehouse = Warehouse.objects.create(name="انبار اصلی", is_default=True)
        self.supplier = Party.objects.create(name="تأمین‌کننده ۱", entity_type=Party.EntityType.COMPANY, is_supplier=True)
        self.partner = Party.objects.create(name="شریک ۱", entity_type=Party.EntityType.COMPANY, is_partner=True)
        self.client_party = Party.objects.create(name="کارفرما ۱", entity_type=Party.EntityType.INDIVIDUAL, is_client=True)

        self.cat = ItemCategory.objects.create(name="دسته اصلی")
        self.item = Item.objects.create(name="لوله مسی", category=self.cat, unit=Item.Unit.METER, reorder_point=5)

        self.project = Project.objects.create(
            name="پروژه تست", code=9901, partner=self.partner, owner=self.client_party, created_by=self.manager,
        )


class PeriodRangeTests(TestCase):
    def test_period_ranges(self):
        t = date(2026, 10, 3)  # 1405/07/11
        start, end = accounting.period_range("this_month", today=t)
        self.assertEqual(start, date(2026, 9, 23))
        self.assertEqual(end, date(2026, 10, 23))

        start, end = accounting.period_range("last_month", today=t)
        self.assertEqual(start, date(2026, 8, 23))
        self.assertEqual(end, date(2026, 9, 23))

        start, end = accounting.period_range("this_year", today=t)
        self.assertEqual(start, date(2026, 3, 21))
        self.assertEqual(end, date(2027, 3, 21))

        start, end = accounting.period_range("all", today=t)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_esfand_edge(self):
        t = date(2027, 3, 10)  # 1405/12/20
        start, end = accounting.period_range("this_month", today=t)
        self.assertEqual(start, date(2027, 2, 20))
        self.assertEqual(end, date(2027, 3, 21))

    def test_farvardin_edge(self):
        t = date(2026, 3, 25)  # 1405/01/05
        start, end = accounting.period_range("last_month", today=t)
        self.assertEqual(start, date(2026, 2, 20))
        self.assertEqual(end, date(2026, 3, 21))





class StockMovementDirectionTests(BaseAccountingTestCase):
    def test_directions(self):
        lot = receive_stock(
            item=self.item, warehouse=self.warehouse, qty=Decimal("10"),
            unit_cost=Decimal("1000"), received_at=timezone.now(),
        )
        m_in = StockMovement.objects.filter(lot=lot, movement_type=StockMovement.MovementType.IN).first()
        self.assertIsNotNone(m_in)
        self.assertEqual(m_in.direction, StockMovement.Direction.IN)

        consume_stock(item=self.item, qty=Decimal("2"), user=self.accountant, notes="مصرف تست")
        m_out = StockMovement.objects.filter(movement_type=StockMovement.MovementType.OUT).first()
        self.assertIsNotNone(m_out)
        self.assertEqual(m_out.direction, StockMovement.Direction.OUT)

        record_manual_stock_change(
            item=self.item, kind="adjust_decrease", qty_raw="1", notes="تعدیل کاهشی", user=self.accountant,
        )
        m_adj_dec = StockMovement.objects.filter(movement_type=StockMovement.MovementType.ADJUST, direction=StockMovement.Direction.OUT).first()
        self.assertIsNotNone(m_adj_dec)
        self.assertEqual(m_adj_dec.movement_type, StockMovement.MovementType.ADJUST)
        self.assertEqual(m_adj_dec.direction, StockMovement.Direction.OUT)

        record_manual_stock_change(
            item=self.item, kind="adjust_increase", qty_raw="3", notes="تعدیل افزایشی", user=self.accountant, unit_cost_raw="1200",
        )
        m_adj_inc = StockMovement.objects.filter(movement_type=StockMovement.MovementType.ADJUST, direction=StockMovement.Direction.IN).first()
        self.assertIsNotNone(m_adj_inc)
        self.assertEqual(m_adj_inc.movement_type, StockMovement.MovementType.ADJUST)
        self.assertEqual(m_adj_inc.direction, StockMovement.Direction.IN)

        record_manual_stock_change(
            item=self.item, kind="opening", qty_raw="5", notes="موجودی اول دوره", user=self.accountant, unit_cost_raw="1500",
        )
        m_open = StockMovement.objects.filter(movement_type=StockMovement.MovementType.OPENING).first()
        self.assertIsNotNone(m_open)
        self.assertEqual(m_open.direction, StockMovement.Direction.IN)


class OpeningStockTests(BaseAccountingTestCase):
    def test_opening_validation_and_flow(self):
        with self.assertRaises(ValueError) as ctx:
            record_manual_stock_change(
                item=self.item, kind="opening", qty_raw="5", notes="بدون بها", user=self.accountant, unit_cost_raw="",
            )
        self.assertIn("بهای واحد را وارد کنید", str(ctx.exception))

        record_manual_stock_change(
            item=self.item, kind="opening", qty_raw="10", notes="اولیه با بها", user=self.accountant, unit_cost_raw="2000",
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("10"))
        self.assertEqual(self.item.moving_average_cost, Decimal("2000"))

        self.client.force_login(self.accountant)
        get_res = self.client.get(reverse("inventory:stock_movement_new"))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'value="opening"')

        post_res = self.client.post(reverse("inventory:stock_movement_new"), {
            "item_id": self.item.id,
            "kind": "opening",
            "qty": "5",
            "unit_cost": "2500",
            "notes": "ثبت تستی فرم",
        })
        self.assertEqual(post_res.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("15"))


class OverviewNumbersTests(BaseAccountingTestCase):
    def test_overview_numbers(self):
        create_purchase_from_form(
            supplier_party_id=self.supplier.id, invoice_number="PUR-01", invoice_file=None,
            purchased_at=timezone.now(), notes="خرید رسمی", lines_raw=[{"id": self.item.id, "warehouse_id": self.warehouse.id, "qty": "10", "unit_cost": "1000"}],
        )

        record_manual_stock_change(
            item=self.item, kind="opening", qty_raw="5", notes="موجودی اول دوره", user=self.accountant, unit_cost_raw="2000",
        )

        consume_stock(item=self.item, qty=Decimal("2"), user=self.accountant, notes="مصرف بدون پروژه")

        record_manual_stock_change(
            item=self.item, kind="adjust_decrease", qty_raw="1", notes="تعدیل کسری", user=self.accountant,
        )

        stats = accounting.accounting_overview("all")
        self.assertEqual(stats["purchases"], Decimal("10000"))
        self.assertEqual(stats["opening"], Decimal("10000"))
        self.assertEqual(stats["consumption"], Decimal("2000"))
        self.assertEqual(stats["adjust_loss"], Decimal("1000"))
        self.assertEqual(stats["stock_value"], Decimal("17000"))
        self.assertEqual(stats["consumption_unlinked"], Decimal("2000"))

        stats_past = accounting.accounting_overview("this_month", today=date(2020, 5, 5))
        self.assertEqual(stats_past["purchases"], Decimal("0"))
        self.assertEqual(stats_past["opening"], Decimal("0"))
        self.assertEqual(stats_past["consumption"], Decimal("0"))

        consume_stock(item=self.item, qty=Decimal("1"), user=self.accountant, notes="مصرف پروژه", related_object=self.project)
        stats_after = accounting.accounting_overview("all")
        self.assertEqual(stats_after["consumption_unlinked"], Decimal("2000"))
        self.assertEqual(stats_after["consumption"], Decimal("3000"))

        # Suspend project -> consumption and sales excluded from accounting_overview
        from projects.services import suspend_stage
        step_first = self.project.stages.first()
        if step_first:
            suspend_stage(step_first, actor=self.admin_user, comment="تعلیق")
            stats_held = accounting.accounting_overview("all")
            self.assertEqual(stats_held["consumption"], Decimal("2000"))
            self.assertEqual(stats_held["consumption_unlinked"], Decimal("2000"))


class ProjectFinancialsTests(BaseAccountingTestCase):
    def test_project_financials_calculations(self):
        inv = Invoice.objects.create(
            project=self.project, number="INV-PRJ-1", billed_party=self.client_party,
            total_amount=Decimal("1000000"), issue_date=timezone.localdate(),
        )

        receive_stock(
            item=self.item, warehouse=self.warehouse, qty=Decimal("10"), unit_cost=Decimal("1000"),
            received_at=timezone.now(),
        )

        consume_stock(
            item=self.item, qty=Decimal("3"), user=self.accountant, notes="مصرف برای پروژه", related_object=self.project,
        )

        ProjectCost.objects.create(
            project=self.project, kind=ProjectCost.Kind.OTHER, title="کرایه حمل", amount=Decimal("500"), created_by=self.accountant,
        )

        record_manual_stock_change(
            item=self.item, kind="adjust_increase", qty_raw="1", notes="برگشت به انبار", user=self.accountant,
            unit_cost_raw="1000", related_object=self.project,
        )

        p = accounting.projects_financial_queryset().get(pk=self.project.pk)
        self.assertEqual(p.revenue, Decimal("1000000"))
        self.assertEqual(p.stock_out, Decimal("3000"))
        self.assertEqual(p.stock_back, Decimal("1000"))
        self.assertEqual(p.rec_costs, Decimal("500"))
        self.assertEqual(p.actual_cost, Decimal("2500"))
        self.assertEqual(p.net_result, Decimal("997500"))

        p.invoice.status = Invoice.Status.CANCELLED
        p.invoice.save()
        p_cancelled = accounting.projects_financial_queryset().get(pk=self.project.pk)
        self.assertEqual(p_cancelled.revenue, Decimal("0"))

        new_project = Project.objects.create(name="پروژه بدون فاکتور", code=9902, partner=self.partner, owner=self.client_party)
        p_no_inv = accounting.projects_financial_queryset().get(pk=new_project.pk)
        self.assertEqual(p_no_inv.revenue, Decimal("0"))


class ReconciliationTests(BaseAccountingTestCase):
    def setUp(self):
        super().setUp()
        receive_stock(
            item=self.item, warehouse=self.warehouse, qty=Decimal("100"), unit_cost=Decimal("1000"), received_at=timezone.now(),
        )
        self.wt = WorkflowTemplate.objects.create(name="قالب تست", is_default=True)
        self.step = WorkflowStepTemplate.objects.create(
            template=self.wt, title="مرحله نصب", kind=StageKind.INSTALL, order=1,
        )
        self.stage = ProjectStage.objects.create(
            project=self.project, step_template=self.step, title="مرحله نصب", kind=StageKind.INSTALL, order=1,
        )
        from catalog.models import Service
        self.catalog_service = Service.objects.create(name="خدمت نصب")
        self.service = ProjectService.objects.create(project=self.project, service=self.catalog_service, qty=1, unit_price=Decimal("10000"))
        self.mat = ProjectServiceMaterial.objects.create(
            service_line=self.service, item=self.item, qty=Decimal("10"), cost_snapshot=Decimal("1000"),
        )

    def row(self, item=None):
        item = item or self.item
        return next(r for r in accounting.project_reconciliation(self.project) if r["item"].pk == item.pk)

    def consume(self, item, qty):
        consume_stock(item=item, qty=Decimal(qty), user=self.accountant, notes="مصرف", related_object=self.project)

    def test_reconciliation_follows_stage_usage(self):
        self.assertEqual(accounting.project_reconciliation(self.project), [])   # فقط پیش‌فاکتور؛ مصرفی نیست
        StageUsage.objects.create(stage=self.stage, item=self.item, qty=Decimal("12"))
        r = self.row()
        self.assertEqual((r["basis"], r["planned"], r["used"], r["expected"], r["status"]),
                         ("usage", Decimal("10"), Decimal("12"), Decimal("12"), "short"))
        self.consume(self.item, "5")
        r = self.row()
        self.assertEqual((r["status"], r["unsettled"]), ("short", Decimal("7")))
        self.consume(self.item, "7")
        self.assertEqual(self.row()["status"], "ok")
        self.consume(self.item, "2")
        r = self.row()
        self.assertEqual((r["status"], r["unsettled"]), ("over", Decimal("-2")))

    def test_usage_of_two_stages_is_summed_per_stage(self):
        step2 = WorkflowStepTemplate.objects.create(template=self.wt, title="مرحله دوم", kind=StageKind.SHIPPING, order=2)
        stage2 = ProjectStage.objects.create(project=self.project, step_template=step2, title="مرحله دوم",
                                             kind=StageKind.SHIPPING, order=2)
        StageUsage.objects.create(stage=self.stage, item=self.item, qty=Decimal("4.5"))
        StageUsage.objects.create(stage=stage2, item=self.item, qty=Decimal("3"))
        r = self.row()
        self.assertEqual(r["expected"], Decimal("7.5"))
        self.assertEqual([(b["stage"].pk, b["qty"]) for b in r["by_stage"]],
                         [(self.stage.pk, Decimal("4.5")), (stage2.pk, Decimal("3"))])
        self.assertEqual(r["expected_input"], "7.5")

    def test_manual_only_item_keeps_its_deducted_quantity(self):
        other = Item.objects.create(name="کالای دستی", category=self.cat, unit=Item.Unit.PIECE)
        receive_stock(item=other, warehouse=self.warehouse, qty=Decimal("10"), unit_cost=Decimal("500"),
                      received_at=timezone.now())
        self.consume(other, "4")
        r = self.row(other)
        self.assertEqual((r["basis"], r["expected"], r["status"]), ("manual", Decimal("4"), "ok"))


class AccountantPaymentVisibilityTests(BaseAccountingTestCase):
    def test_accountant_can_view_and_decide_others_payments(self):
        inv = Invoice.objects.create(
            project=self.project, number="INV-PAY-1", billed_party=self.client_party,
            total_amount=Decimal("500000"), issue_date=timezone.localdate(),
        )
        payment = Payment.objects.create(
            invoice=inv, amount=Decimal("500000"), method=Payment.Method.CARD_TO_CARD,
            status=Payment.Status.PENDING,
        )

        self.client.force_login(self.accountant)
        detail_res = self.client.get(reverse("finance:payment_detail", args=[payment.id]))
        self.assertEqual(detail_res.status_code, 200)

        decide_res = self.client.post(reverse("finance:payment_decide", args=[payment.id]), {
            "action": "approve",
            "verified_amount": "500000",
        })
        self.assertEqual(decide_res.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.APPROVED)

        self.client.force_login(self.tech)
        other_detail = self.client.get(reverse("finance:payment_detail", args=[payment.id]))
        self.assertEqual(other_detail.status_code, 302)



