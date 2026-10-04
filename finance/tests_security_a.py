import jdatetime
from decimal import Decimal
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, Service
from core.models import Party, Specialty
from finance import accounting
from finance.models import Payment
from finance.reports import generate_periodic_financial_report, get_jalali_date_range
from finance.services import approve_payment
from inventory.models import StockMovement, Warehouse
from inventory.services import receive_stock, record_manual_stock_change
from projects.models import Project, ProjectStage, StageApproval, WorkflowStepTemplate, WorkflowTemplate, PartRequest
from projects.services import create_project_from_technician_intake, update_project_from_technician_edit


class SecurityBase(TestCase):
    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        tpl = WorkflowTemplate.objects.create(name="قالب امنیت", is_default=True)
        WorkflowStepTemplate.objects.create(template=tpl, order=1, title="صدور پیش‌فاکتور")
        WorkflowStepTemplate.objects.create(template=tpl, order=2, title="تایید پیش‌فاکتور", requires_payment_selection=True)

        sp = lambda n: Specialty.objects.get_or_create(name=n)[0]
        self.tech = User.objects.create_user(username="sec_tech", phone_number="09127770001", password="pw",
                                             role=User.Role.EMPLOYEE, is_staff=True)
        self.tech.specialties.add(sp("پذیرش"))
        self.accountant = User.objects.create_user(username="sec_acc", phone_number="09127770002", password="pw",
                                                   role=User.Role.EMPLOYEE, is_staff=True)
        self.accountant.specialties.add(sp("حسابدار"))
        self.manager = User.objects.create_user(username="sec_mgr", phone_number="09127770003", password="pw",
                                                role=User.Role.ADMIN, is_staff=True)
        self.keeper = User.objects.create_user(username="sec_wh", phone_number="09127770004", password="pw",
                                               role=User.Role.EMPLOYEE, is_staff=True)
        self.keeper.specialties.add(sp("انباردار"))

        self.party = Party.objects.create(name="مشتری امنیت", phone_number="09127770005", is_client=True)
        self.service = Service.objects.create(name="خدمت امنیت")
        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=self.party.id,
            service_lines=[{"id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            material_lines=[], send_sms=False,
        )
        self.owner = User.objects.get(phone_number="09127770005")   # حساب خودکار مشتری
        self.admin_user = self.manager


class PortalSecurityTests(SecurityBase):
    def test_staff_employee_cannot_view_invoice_or_pay(self):
        c = Client(); c.force_login(self.tech)
        uid = self.invoice.uuid
        self.assertEqual(c.get(reverse("finance:portal_invoice_detail", args=[uid])).status_code, 404)
        self.assertEqual(c.get(reverse("finance:portal_invoice_pdf", args=[uid])).status_code, 404)
        r = c.post(reverse("finance:portal_add_payment", args=[uid]), {"payment_method": "credit", "payment_note": "x"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_accountant_views_but_cannot_pay_as_customer(self):
        c = Client(); c.force_login(self.accountant)
        uid = self.invoice.uuid
        self.assertEqual(c.get(reverse("finance:portal_invoice_detail", args=[uid])).status_code, 200)
        r = c.post(reverse("finance:portal_add_payment", args=[uid]), {"payment_method": "credit", "payment_note": "x"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Payment.objects.count(), 0)

    def test_owner_still_pays(self):
        c = Client(); c.force_login(self.owner)
        r = c.post(reverse("finance:portal_add_payment", args=[self.invoice.uuid]),
                   {"payment_method": "credit", "payment_note": "تسویه آخر ماه", "payment_amount": "100000"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)

    def _approval(self):
        stage = self.project.stages.get(order=2)
        stage.status = ProjectStage.Status.WAITING_APPROVAL
        stage.save()
        return StageApproval.objects.create(stage=stage, sent_to_party=self.party)

    def test_stage_approval_staff_can_only_view(self):
        approval = self._approval()
        url = reverse("projects:portal_stage_approval", args=[approval.id])
        c = Client()
        c.force_login(self.tech)
        self.assertEqual(c.get(url).status_code, 404)
        c.force_login(self.accountant)
        resp = c.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "فقط برای مشاهده است")
        self.assertEqual(c.post(url, {"action": "reject", "comment": "x"}).status_code, 404)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, StageApproval.Decision.PENDING)


class PricingGuardTests(SecurityBase):
    def test_reception_cannot_change_prices_but_can_edit_notes(self):
        with self.assertRaises(ValueError):
            update_project_from_technician_edit(project=self.project, actor=self.tech, installation_fee_raw="1000")
        with self.assertRaises(ValueError):
            update_project_from_technician_edit(project=self.project, actor=self.tech, contract_date=None)
        with self.assertRaises(ValueError):
            update_project_from_technician_edit(project=self.project, actor=self.tech, service_lines=[])
        project, _ = update_project_from_technician_edit(project=self.project, actor=self.tech, notes="فقط یادداشت")
        self.assertEqual(project.notes, "فقط یادداشت")

    def test_manager_can_change_prices(self):
        project, rebuilt = update_project_from_technician_edit(
            project=self.project, actor=self.manager, installation_fee_raw="300000")
        self.assertTrue(rebuilt)

    def test_tampered_post_by_reception_changes_nothing(self):
        c = Client(); c.force_login(self.tech)
        before = self.project.services.count()
        c.post(reverse("projects:project_edit", args=[self.project.id]),
               {"services_json": "[]", "installation_fee": "999"})
        self.project.refresh_from_db()
        self.assertEqual(self.project.services.count(), before)
        self.assertEqual(self.project.installation_fee, Decimal("0"))


class InternalConsumptionTests(SecurityBase):
    def setUp(self):
        super().setUp()
        self.wh = Warehouse.objects.create(name="انبار", is_default=True)
        self.item = Item.objects.create(name="کالای مصرف", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=1000, received_at=timezone.now())

    def test_consume_without_project_or_internal_is_refused(self):
        with self.assertRaises(ValueError):
            record_manual_stock_change(item=self.item, kind="consume", qty_raw="1", notes="x", user=self.keeper)

    def test_internal_consumption_is_unlinked_and_not_billed_to_any_project(self):
        record_manual_stock_change(item=self.item, kind="consume", qty_raw="1", notes="x", user=self.keeper, internal=True)
        move = StockMovement.objects.get(movement_type=StockMovement.MovementType.OUT)
        self.assertIsNone(move.related_content_type)
        self.assertEqual(accounting.accounting_overview("all")["consumption_unlinked"], Decimal("1000"))
        self.assertEqual(accounting.projects_financial_queryset().get(pk=self.project.pk).stock_out, Decimal("0"))

    def test_view_requires_explicit_choice(self):
        c = Client(); c.force_login(self.keeper)
        c.post(reverse("inventory:stock_movement_new"),
               {"item_id": self.item.id, "kind": "consume", "qty": "2", "notes": "x", "project_id": ""})
        self.assertEqual(self.item.current_stock, Decimal("10"))
        c.post(reverse("inventory:stock_movement_new"),
               {"item_id": self.item.id, "kind": "consume", "qty": "2", "notes": "x", "project_id": "company"})
        self.assertEqual(self.item.current_stock, Decimal("8"))


class ReportsAndPagesTests(SecurityBase):
    def test_report_counts_proforma_sales_and_payments_without_paid_at(self):
        pay = Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100000,
                                     claimed_amount=100000, reference_number="R-1")
        approve_payment(pay, approved_by=self.accountant, verified_amount="100000")
        self.assertIsNone(Payment.objects.get(pk=pay.pk).paid_at)
        today = jdatetime.date.fromgregorian(date=timezone.localdate()).strftime("%Y/%m/%d")
        start_g, end_g = get_jalali_date_range(today, today)
        report = generate_periodic_financial_report(start_g, end_g)
        self.assertEqual(report["total_revenue"], Decimal("1000000"))
        self.assertEqual(report["total_received"], Decimal("100000"))

    def test_supplier_pages_render(self):
        c = Client(); c.force_login(self.manager)
        for name in ("finance:accounting_suppliers", "finance:accounting_suppliers_table"):
            self.assertEqual(c.get(reverse(name)).status_code, 200, name)

    def test_customers_center_lists_billed_partner(self):
        partner = Party.objects.create(name="شریک فاکتورخور", phone_number="09127770009", is_partner=True)
        create_project_from_technician_intake(
            created_by=self.tech, party_id=partner.id,
            service_lines=[{"id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("500000")}],
            material_lines=[], send_sms=False)
        c = Client(); c.force_login(self.accountant)
        resp = c.get(reverse("finance:accounting_customers"), {"client_id": partner.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["selected_client"], partner)
        self.assertIn(partner, list(resp.context["clients"]))
        self.assertEqual(c.get(reverse("finance:accounting_customers"), {"client_id": "abc"}).status_code, 404)

    def test_part_request_detail_hides_money_from_plain_keeper(self):
        wh = Warehouse.objects.create(name="انبار ۲", is_default=True)
        item = Item.objects.create(name="قطعه خاص", item_type=Item.ItemType.MATERIAL)
        receive_stock(item=item, warehouse=wh, qty=10, unit_cost=1000, received_at=timezone.now())
        stage = self.project.stages.first()
        req = PartRequest.objects.create(project=self.project, stage=stage, item=item, qty=1, requested_by=self.tech,
                                         status=PartRequest.Status.ISSUED, cost_total=Decimal("1000"), sale_total=Decimal("1500"))
        c = Client()
        c.force_login(self.keeper)
        resp = c.get(reverse("projects:part_request_detail", args=[req.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "بهای تمام‌شده")
        self.assertNotContains(resp, "جمع فروش")

        c.force_login(self.accountant)
        resp_acc = c.get(reverse("projects:part_request_detail", args=[req.id]))
        self.assertEqual(resp_acc.status_code, 200)
        self.assertContains(resp_acc, "بهای تمام‌شده")
        self.assertContains(resp_acc, "جمع فروش")
