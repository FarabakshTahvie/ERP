from decimal import Decimal
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, Service
from core.models import Party, Specialty
from inventory.models import StockLot, StockMovement, Warehouse
from inventory.services import receive_stock, consume_stock, record_manual_stock_change
from projects.models import (
    Project, ProjectStage, StageKind, ProjectService, ProjectServiceMaterial,
    InstallLine, PartRequest, ExtraShipment,
)
from projects.ops import ensure_install_lines, set_install_line
from projects.services import advance_stage, create_project_from_technician_intake
from projects.workflow_v2 import build_workflow_v2
from finance.models import Invoice, InvoiceLine, Payment, AccountingEvent
from finance import accounting
from utils.test_helpers import make_image_file


class P2BaseScenarioMixin:
    def setup_scenario(self):
        self.partner = Party.objects.create(name="شریک تستی سناریو", is_partner=True, phone_number="09129990001")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")

        self.accountant = User.objects.create_user(username="acc_p2_tester", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.creator = User.objects.create_user(username="tech_p2_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)

        self.warehouse, _ = Warehouse.objects.get_or_create(name="انبار مرکزی", defaults={"is_default": True})
        if not self.warehouse.is_default:
            self.warehouse.is_default = True
            self.warehouse.save()

        # کالای فلنج با 30 عدد به بهای 920,000
        self.item = Item.objects.create(name="فلنج", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("920000"))
        receive_stock(
            item=self.item, warehouse=self.warehouse, qty=Decimal("30"),
            unit_cost=Decimal("920000"), received_at=timezone.now(),
            movement_type=StockMovement.MovementType.IN, created_by=self.accountant,
        )

        self.service = Service.objects.create(name="خدمت فلنج‌کاری")

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id,
            visit_date=timezone.localdate(), issue_proforma=False,
        )

        ps = ProjectService.objects.create(project=self.project, service=self.service, qty=1, unit_price=Decimal("12276000"))
        ProjectServiceMaterial.objects.create(
            service_line=ps, item=self.item, qty=Decimal("12"),
            cost_snapshot=Decimal("920000"), margin_percent=Decimal("0"),
            line_total=Decimal("11040000"),
        )

        self.invoice = Invoice.objects.create(
            project=self.project, billed_party=self.partner,
            number="INV-P2-001", total_amount=Decimal("12276000"),
            paid_amount=Decimal("0"), status=Invoice.Status.SENT,
            issue_date=timezone.localdate(),
        )
        InvoiceLine.objects.create(
            invoice=self.invoice, line_type=InvoiceLine.LineType.SERVICE,
            title="خدمت فلنج‌کاری", qty=Decimal("1"), unit_price=Decimal("12276000"),
            total=Decimal("12276000"),
        )

        self.credit_payment = Payment.objects.create(
            invoice=self.invoice, method=Payment.Method.CREDIT,
            amount=Decimal("12276000"), claimed_amount=Decimal("12276000"),
            status=Payment.Status.APPROVED, approved_by=self.accountant,
            approved_at=timezone.now(),
        )

        install_stage = self.project.stages.get(kind=StageKind.INSTALL)
        install_stage.status = ProjectStage.Status.IN_PROGRESS
        install_stage.assigned_to = self.creator
        install_stage.save()
        ensure_install_lines(install_stage)
        mat_line = install_stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)
        set_install_line(line=mat_line, status="ok", actual_qty_raw="11", reason="", actor=self.creator)

        consume_stock(
            item=self.item, qty=Decimal("9"), user=self.creator,
            related_object=self.project, notes="درخواست قطعه تحویلی",
        )


class P2PnlNumbersTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_pnl_numbers_before_settlement(self):
        fin = accounting.projects_financial_queryset().get(pk=self.project.pk)
        recon = accounting.project_reconciliation(self.project)
        pnl = accounting.project_pnl(fin, recon)

        self.assertEqual(pnl["revenue"], Decimal("12276000"))
        self.assertEqual(pnl["collected"], Decimal("0"))
        self.assertEqual(pnl["remaining"], Decimal("12276000"))
        self.assertEqual(pnl["stock_cost"], Decimal("8280000"))
        self.assertEqual(pnl["pending_cost"], Decimal("1840000"))
        self.assertEqual(pnl["profit_booked"], Decimal("3996000"))
        self.assertEqual(pnl["profit_projected"], Decimal("2156000"))
        self.assertEqual(pnl["cash_position"], Decimal("-8280000"))
        self.assertEqual(pnl["state"], "provisional")

        r = recon[0]
        self.assertEqual(r["expected"], Decimal("11"))
        self.assertEqual(r["net_out"], Decimal("9"))
        self.assertEqual(r["unsettled"], Decimal("2"))
        self.assertEqual(r["variance"], Decimal("-920000"))


class P2SettlementTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_settle_with_suggested_qty(self):
        applied = accounting.settle_project_materials(
            project=self.project, final_qtys={}, reasons={}, actor=self.accountant
        )
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0], ("فلنج", Decimal("2")))

        ct = accounting.ContentType.objects.get_for_model(Project)
        total_out = StockMovement.objects.filter(
            related_content_type=ct, related_object_id=self.project.pk, direction=StockMovement.Direction.OUT
        ).aggregate(t=accounting.Sum("qty"))["t"]
        self.assertEqual(total_out, Decimal("11"))

        fin = accounting.projects_financial_queryset().get(pk=self.project.pk)
        recon = accounting.project_reconciliation(self.project)
        self.assertTrue(all(r["status"] == "ok" for r in recon))
        self.assertEqual(fin.stock_out, Decimal("10120000"))

    def test_settle_more_consumed_with_reason(self):
        applied = accounting.settle_project_materials(
            project=self.project, final_qtys={self.item.pk: Decimal("20")},
            reasons={self.item.pk: "مصرف اضافه با تایید"}, actor=self.accountant
        )
        self.assertEqual(applied[0], ("فلنج", Decimal("11")))
        fin = accounting.projects_financial_queryset().get(pk=self.project.pk)
        recon = accounting.project_reconciliation(self.project)
        pnl = accounting.project_pnl(fin, recon)
        self.assertEqual(pnl["profit_booked"], Decimal("-6124000"))

    def test_settle_less_consumed_creates_return_movement(self):
        applied = accounting.settle_project_materials(
            project=self.project, final_qtys={self.item.pk: Decimal("8")},
            reasons={self.item.pk: "برگشت قطعه"}, actor=self.accountant
        )
        self.assertEqual(applied[0], ("فلنج", Decimal("-1")))
        ct = accounting.ContentType.objects.get_for_model(Project)
        ret_move = StockMovement.objects.filter(
            related_content_type=ct, related_object_id=self.project.pk,
            movement_type=StockMovement.MovementType.RETURN
        ).first()
        self.assertIsNotNone(ret_move)
        self.assertEqual(ret_move.direction, StockMovement.Direction.IN)
        self.assertEqual(ret_move.qty, Decimal("1"))
        self.assertEqual(ret_move.unit_cost, Decimal("920000"))

        fin = accounting.projects_financial_queryset().get(pk=self.project.pk)
        self.assertEqual(fin.actual_cost, Decimal("7360000"))

    def test_settle_without_reason_when_changed_fails_atomically(self):
        with self.assertRaises(ValueError):
            accounting.settle_project_materials(
                project=self.project, final_qtys={self.item.pk: Decimal("15")},
                reasons={}, actor=self.accountant
            )
        ct = accounting.ContentType.objects.get_for_model(Project)
        self.assertEqual(StockMovement.objects.filter(related_content_type=ct, related_object_id=self.project.pk).count(), 1)

    def test_settle_insufficient_stock_fails(self):
        with self.assertRaises(ValueError):
            accounting.settle_project_materials(
                project=self.project, final_qtys={self.item.pk: Decimal("100")},
                reasons={self.item.pk: "مصرف بسیار زیاد"}, actor=self.accountant
            )

    def test_settle_unauthorized_user_fails(self):
        with self.assertRaises(ValueError):
            accounting.settle_project_materials(
                project=self.project, final_qtys={}, reasons={}, actor=self.creator
            )

    def test_settle_twice_is_noop(self):
        accounting.settle_project_materials(project=self.project, final_qtys={}, reasons={}, actor=self.accountant)
        ct = accounting.ContentType.objects.get_for_model(Project)
        count_before = StockMovement.objects.filter(related_content_type=ct, related_object_id=self.project.pk).count()
        applied = accounting.settle_project_materials(project=self.project, final_qtys={}, reasons={}, actor=self.accountant)
        self.assertEqual(applied, [])
        self.assertEqual(StockMovement.objects.filter(related_content_type=ct, related_object_id=self.project.pk).count(), count_before)

    def test_final_review_view_flow(self):
        final_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        final_stage.status = ProjectStage.Status.IN_PROGRESS
        final_stage.assigned_to = self.accountant
        final_stage.save()

        client = Client()
        client.force_login(self.accountant)
        resp = client.post(reverse("projects:final_review", args=[self.project.id]), {
            "comment": "تایید نهایی پروژه و تحویل به کارفرما",
            f"final_qty_{self.item.id}": "11",
        })
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETED)
        self.assertTrue(AccountingEvent.objects.filter(project=self.project, kind=AccountingEvent.Kind.SETTLEMENT).exists())

    def test_final_review_blocked_with_pending_extras_or_parts(self):
        shipping_stage = self.project.stages.get(kind=StageKind.SHIPPING)
        ExtraShipment.objects.create(project=self.project, stage=shipping_stage, item=self.item, qty=Decimal("1"),
                                    cost_snapshot=Decimal("920000"),
                                    disposition=ExtraShipment.Disposition.PENDING)
        final_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        final_stage.status = ProjectStage.Status.IN_PROGRESS
        final_stage.save()

        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("projects:final_review", args=[self.project.id]))
        self.assertContains(resp, "تایید نهایی غیرفعال است")


class P2InvoiceAdjustmentTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_add_invoice_adjustment_increase(self):
        accounting.add_invoice_adjustment(
            invoice=self.invoice, title="هزینه داربست اضافه", amount_raw="100000",
            kind="increase", reason="نیاز به داربست بیشتر", actor=self.accountant
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal("12376000"))
        line = self.invoice.lines.filter(title="هزینه داربست اضافه").first()
        self.assertIsNotNone(line)
        self.assertTrue(line.is_manual)
        self.assertEqual(self.invoice.status, Invoice.Status.SENT)
        self.assertIsNone(self.invoice.settled_at)

    def test_add_invoice_adjustment_decrease_below_paid_fails(self):
        self.invoice.paid_amount = Decimal("10000000")
        self.invoice.save()
        with self.assertRaises(ValueError):
            accounting.add_invoice_adjustment(
                invoice=self.invoice, title="تخفیف کلی", amount_raw="3000000",
                kind="decrease", reason="تخفیف زیاد", actor=self.accountant
            )

    def test_add_invoice_adjustment_without_reason_fails(self):
        with self.assertRaises(ValueError):
            accounting.add_invoice_adjustment(
                invoice=self.invoice, title="اضافه", amount_raw="10000",
                kind="increase", reason="", actor=self.accountant
            )

    def test_add_invoice_adjustment_unauthorized_fails(self):
        with self.assertRaises(ValueError):
            accounting.add_invoice_adjustment(
                invoice=self.invoice, title="اضافه", amount_raw="10000",
                kind="increase", reason="دلیل", actor=self.creator
            )


class P2CreditSettlementTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_credit_open_amount_and_labels(self):
        self.assertEqual(self.credit_payment.credit_open_amount, Decimal("12276000"))
        self.assertEqual(self.credit_payment.status_label, "اعتباری — منتظر تسویه")
        self.assertEqual(self.credit_payment.status_variant, "warning")

    def test_settle_partial_credit_payment(self):
        settlement = accounting.settle_credit_payment(
            credit=self.credit_payment, method=Payment.Method.CARD_TO_CARD,
            amount_raw="5000000", reference_number="REF-123456",
            receipt_file=make_image_file(), actor=self.accountant
        )
        self.invoice.refresh_from_db()
        self.credit_payment.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("5000000"))
        self.assertEqual(self.credit_payment.credit_open_amount, Decimal("7276000"))
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

    def test_settle_full_credit_payment(self):
        accounting.settle_credit_payment(
            credit=self.credit_payment, method=Payment.Method.CARD_TO_CARD,
            amount_raw="12276000", reference_number="REF-ALL",
            receipt_file=make_image_file(), actor=self.accountant
        )
        self.credit_payment.refresh_from_db()
        self.assertEqual(self.credit_payment.credit_open_amount, Decimal("0"))
        self.assertEqual(self.credit_payment.status_label, "اعتباری — تسویه‌شده")
        self.assertEqual(self.credit_payment.status_variant, "success")

    def test_settle_more_than_open_fails(self):
        with self.assertRaises(ValueError):
            accounting.settle_credit_payment(
                credit=self.credit_payment, method=Payment.Method.CARD_TO_CARD,
                amount_raw="20000000", reference_number="REF-OVER",
                receipt_file=make_image_file(), actor=self.accountant
            )

    def test_credit_open_total_excludes_cancelled_invoices(self):
        self.assertEqual(accounting.credit_open_total(), Decimal("12276000"))
        self.invoice.status = Invoice.Status.CANCELLED
        self.invoice.save()
        self.assertEqual(accounting.credit_open_total(), Decimal("0"))


class P2IntegrityTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_normal_flow_integrity_diff_zero(self):
        integ = accounting.stock_integrity()
        self.assertEqual(integ["diff"], Decimal("0"))

    def test_tampered_lot_integrity_diff_nonzero(self):
        lot = StockLot.objects.filter(item=self.item).first()
        lot.qty_remaining = Decimal("100")
        lot.save()
        integ = accounting.stock_integrity()
        self.assertNotEqual(integ["diff"], Decimal("0"))


class P2CostPermissionTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_accountant_can_manage_costs_after_final_review(self):
        from projects import ops
        cost = ops.add_project_cost(
            project=self.project, kind="other", title="هزینه پیک",
            amount_raw="50000", actor=self.accountant
        )
        self.assertEqual(cost.amount, Decimal("50000"))
        ops.delete_project_cost(cost=cost, actor=self.accountant)

    def test_creator_cannot_add_cost_after_review_closed(self):
        from projects import ops
        review_st = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        review_st.status = ProjectStage.Status.DONE
        review_st.save()
        with self.assertRaises(ValueError):
            ops.add_project_cost(
                project=self.project, kind="other", title="تست",
                amount_raw="1000", actor=self.creator
            )


class P2ProjectsTableTests(P2BaseScenarioMixin, TestCase):
    def setUp(self):
        self.setup_scenario()

    def test_projects_table_context(self):
        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("finance:accounting_projects"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "دریافتی (تومان)")
        self.assertContains(resp, "حساب")
