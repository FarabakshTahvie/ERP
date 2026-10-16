import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from projects.models import Project, ProjectParticipant, WorkflowTemplate, WorkflowStepTemplate
from projects.services import (
    create_project_from_technician_intake, update_project_from_technician_edit, parse_fee
)
from finance.models import InvoiceLine, Payment
from utils.jalali_forms import JalaliDateField


class ProjectCostsAndContractTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="tech_creator_costs", phone_number="09121111111",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.admin_user = User.objects.create_user(
            username="admin_costs", phone_number="09121111112",
            password="AdminPassword123", role=User.Role.ADMIN,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.creator.specialties.add(self.sp_reception)

        self.template = WorkflowTemplate.objects.create(name="قالب پیش‌فرض هزینه‌ها", is_default=True)
        self.step1 = WorkflowStepTemplate.objects.create(template=self.template, order=1, title="صدور پیش‌فاکتور")
        self.step2 = WorkflowStepTemplate.objects.create(
            template=self.template, order=2, title="تایید پیش‌فاکتور", requires_payment_selection=True
        )

        self.service1 = Service.objects.create(name="سرویس اول")
        self.item1 = Item.objects.create(name="متریال اول")
        self.party = Party.objects.create(name="کارفرمای هزینه‌ها", phone_number="09121111113", is_client=True)

        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.party.id,
            location_address="تهران",
            service_lines=[{"id": self.service1.id, "qty": Decimal("2"), "unit_price": Decimal("500000")}],
            material_lines=[{"id": self.item1.id, "qty": Decimal("1"), "unit_price": Decimal("200000")}],
            send_sms=False,
        )

    def test_intake_with_three_fees(self):
        proj, inv, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            installation_fee_raw="300000",
            shipping_fee_raw="100000",
            extra_fee_raw="50000",
            send_sms=False,
        )
        self.assertEqual(proj.installation_fee, Decimal("300000"))
        self.assertEqual(proj.shipping_fee, Decimal("100000"))
        self.assertEqual(proj.extra_fee, Decimal("50000"))
        self.assertEqual(inv.total_amount, Decimal("1450000"))

    def test_parse_fee_validations(self):
        self.assertEqual(parse_fee("۱,۵۰۰,۰۰۰", label="تست"), Decimal("1500000"))
        self.assertEqual(parse_fee("", label="تست"), Decimal("0"))
        self.assertEqual(parse_fee(None, label="تست"), Decimal("0"))
        for invalid in ["10.5", "-5", "abc", "1e5", "NaN", "1" * 13]:
            with self.assertRaises(ValueError):
                parse_fee(invalid, label="تست")

    def test_intake_with_invalid_fee_raises_value_error(self):
        count_before = Project.objects.count()
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=self.creator,
                party_id=self.party.id,
                service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
                installation_fee_raw="abc",
                send_sms=False,
            )
        self.assertEqual(Project.objects.count(), count_before)

    def test_update_fees_open_rebuilds_invoice(self):
        proj, rebuilt = update_project_from_technician_edit(
            project=self.project,
            actor=self.admin_user,
            installation_fee_raw="300000",
            shipping_fee_raw="100000",
            extra_fee_raw="50000",
        )
        self.assertTrue(rebuilt)
        self.project.invoice.refresh_from_db()
        self.assertEqual(self.project.invoice.total_amount, Decimal("1650000"))

    def test_locked_project_raises_value_error_on_fees(self):
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("100000"),
            paid_at=timezone.now(),
            method=Payment.Method.RECEIPT,
            status=Payment.Status.APPROVED,
            approved_by=self.admin_user,
        )
        self.assertFalse(self.project_prices_editable_check())

        with self.assertRaises(ValueError):
            update_project_from_technician_edit(
                project=self.project,
                actor=self.creator,
                installation_fee_raw="500000",
            )
        dt = JalaliDateField().clean("1405/08/01")
        with self.assertRaises(ValueError):
            update_project_from_technician_edit(
                project=self.project,
                actor=self.creator,
                contract_date=dt,
            )

        proj, _ = update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            notes="فقط یادداشت",
        )
        self.assertEqual(proj.notes, "فقط یادداشت")

    def project_prices_editable_check(self):
        from projects.services import project_prices_editable
        return project_prices_editable(self.project)

    def test_participants_cost_regression_in_invoice(self):
        contractor = Party.objects.create(name="پیمانکار تست", phone_number="09129998877", is_contractor=True)
        ProjectParticipant.objects.create(
            project=self.project,
            party=contractor,
            role=ProjectParticipant.ParticipantRole.CONTRACTOR,
            agreed_cost=Decimal("40000"),
        )
        update_project_from_technician_edit(
            project=self.project,
            actor=self.admin_user,
            extra_fee_raw="50000",
        )
        self.project.invoice.refresh_from_db()
        extra_line = self.project.invoice.lines.filter(line_type=InvoiceLine.LineType.EXTRA).first()
        self.assertIsNotNone(extra_line)
        self.assertEqual(extra_line.unit_price, Decimal("90000"))

    def test_edit_post_missing_fields_does_not_zero_out(self):
        self.project.installation_fee = Decimal("300000")
        self.project.save(update_fields=["installation_fee"])
        client = Client()
        client.force_login(self.creator)
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), {
            "address_text": "فقط آدرس جدید",
            "services_json": json.dumps([{"id": self.service1.id, "qty": "2", "unit_price": "500000"}]),
            "materials_json": json.dumps([{"id": self.item1.id, "qty": "1", "unit_price": "200000"}]),
        })
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.installation_fee, Decimal("300000"))
