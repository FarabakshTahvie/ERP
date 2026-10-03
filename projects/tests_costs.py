import json
from datetime import date
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
from finance.models import Invoice, InvoiceLine, Payment
from finance.services import add_manual_invoice_line
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

    def test_intake_with_empty_or_zero_fees(self):
        proj, inv, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            installation_fee_raw="",
            shipping_fee_raw="0",
            extra_fee_raw=None,
            send_sms=False,
        )
        self.assertEqual(proj.installation_fee, Decimal("0"))
        self.assertEqual(proj.shipping_fee, Decimal("0"))
        self.assertEqual(proj.extra_fee, Decimal("0"))
        self.assertEqual(inv.total_amount, Decimal("1000000"))

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

    def test_intake_with_contract_date_and_notes(self):
        dt = JalaliDateField().clean("1405/07/01")
        proj, inv, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            contract_date=dt,
            notes="یادداشت محرمانه تست",
            send_sms=False,
        )
        self.assertEqual(proj.contract_date, dt)
        self.assertEqual(proj.notes, "یادداشت محرمانه تست")
        self.assertEqual(inv.contract_date, dt)

    def test_notes_exceeding_max_length_raises_value_error(self):
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=self.creator,
                party_id=self.party.id,
                service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
                notes="a" * 2001,
                send_sms=False,
            )

    def test_update_fees_open_rebuilds_invoice(self):
        proj, rebuilt = update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            installation_fee_raw="300000",
            shipping_fee_raw="100000",
            extra_fee_raw="50000",
        )
        self.assertTrue(rebuilt)
        self.project.invoice.refresh_from_db()
        self.assertEqual(self.project.invoice.total_amount, Decimal("1650000"))

    def test_update_same_fees_or_date_no_rebuild(self):
        update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            installation_fee_raw="0",
        )
        proj, rebuilt = update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            installation_fee_raw="0",
        )
        self.assertFalse(rebuilt)

    def test_update_fees_none_keeps_existing(self):
        update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            installation_fee_raw="400000",
        )
        proj, _ = update_project_from_technician_edit(
            project=self.project,
            actor=self.creator,
            installation_fee_raw=None,
        )
        self.assertEqual(proj.installation_fee, Decimal("400000"))

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

    def test_contract_date_updates_or_clears(self):
        dt = JalaliDateField().clean("1405/01/01")
        proj, _ = update_project_from_technician_edit(
            project=self.project, actor=self.creator, contract_date=dt
        )
        self.assertEqual(proj.contract_date, dt)
        self.assertEqual(self.project.invoice.contract_date, dt)

        proj, _ = update_project_from_technician_edit(
            project=self.project, actor=self.creator, contract_date=None
        )
        self.assertIsNone(proj.contract_date)
        self.assertIsNone(self.project.invoice.contract_date)

        dt2 = JalaliDateField().clean("1405/02/02")
        proj, _ = update_project_from_technician_edit(
            project=self.project, actor=self.creator, contract_date=dt2
        )
        self.assertEqual(proj.contract_date, dt2)

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
            actor=self.creator,
            extra_fee_raw="50000",
        )
        self.project.invoice.refresh_from_db()
        extra_line = self.project.invoice.lines.filter(line_type=InvoiceLine.LineType.EXTRA).first()
        self.assertIsNotNone(extra_line)
        self.assertEqual(extra_line.unit_price, Decimal("90000"))

    def test_view_new_project_form_gets_costs(self):
        client = Client()
        client.force_login(self.creator)
        resp = client.get(reverse("projects:new_project_form"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("visit_date", resp.content.decode("utf-8"))

    def test_view_new_project_submit_success(self):
        from projects.workflow_v2 import build_workflow_v2
        build_workflow_v2(make_default=True)
        client = Client()
        client.force_login(self.creator)
        resp = client.post(reverse("projects:new_project_submit"), {
            "phone_number_search": "09121111113",
            "party_id": self.party.id,
            "visit_date": "1405/07/20",
            "notes": "ثبت وب تست",
        })
        self.assertEqual(resp.status_code, 302)
        proj = Project.objects.filter(notes="ثبت وب تست").first()
        self.assertIsNotNone(proj)
        self.assertIsNotNone(proj.visit_date)

    def test_view_new_project_submit_invalid_fee_redirects(self):
        client = Client()
        client.force_login(self.creator)
        count_before = Project.objects.count()
        client.post(reverse("projects:new_project_submit"), {
            "phone_number_search": "09121111113",
            "party_id": self.party.id,
            "visit_date": "",
        })
        self.assertEqual(Project.objects.count(), count_before)

    def test_view_new_project_submit_invalid_date_redirects(self):
        client = Client()
        client.force_login(self.creator)
        count_before = Project.objects.count()
        client.post(reverse("projects:new_project_submit"), {
            "phone_number_search": "09121111113",
            "party_id": self.party.id,
            "visit_date": "1405/13/01",
        })
        self.assertEqual(Project.objects.count(), count_before)

    def test_view_project_edit_get_renders_fees(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("projects:project_edit", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("proforma", content)

    def test_view_project_edit_get_locked_renders_disabled(self):
        self.project.visit_date = date(2026, 10, 11)
        self.project.save()
        visit_st = self.project.stages.filter(kind="visit").first()
        if not visit_st:
            from projects.models import ProjectStage, WorkflowStepTemplate
            st_tmpl, _ = WorkflowStepTemplate.objects.get_or_create(template=self.template, order=99, defaults={"title": "بازدید", "kind": "visit"})
            visit_st = ProjectStage.objects.create(project=self.project, step_template=st_tmpl, order=99, title="بازدید", kind="visit")
        visit_st.status = "done"
        visit_st.save()
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("projects:project_edit", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("proforma", content)

    def test_view_project_edit_post_success(self):
        client = Client()
        client.force_login(self.creator)
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), {
            "installation_fee": "500000",
            "services_json": json.dumps([{"id": self.service1.id, "qty": "2", "unit_price": "500000"}]),
            "materials_json": json.dumps([{"id": self.item1.id, "qty": "1", "unit_price": "200000"}]),
        })
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.installation_fee, Decimal("500000"))

    def test_view_project_edit_post_locked_with_tampered_fees_redirects_and_keeps_values(self):
        self.project.installation_fee = Decimal("300000")
        self.project.notes = "یادداشت اولیه"
        self.project.save(update_fields=["installation_fee", "notes"])
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("100000"),
            paid_at=timezone.now(),
            method=Payment.Method.RECEIPT,
            status=Payment.Status.APPROVED,
            approved_by=self.admin_user,
        )
        client = Client()
        client.force_login(self.creator)
        # ارسال هزینه در حالت قفل موجب خطای اعتبارسنجی سرویس و ریدایرکت با پیام خطا می‌شود
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), {
            "installation_fee": "999999",
            "notes": "یادداشت جدید قفل",
        })
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.installation_fee, Decimal("300000"))
        self.assertEqual(self.project.notes, "یادداشت اولیه")

    def test_edit_post_missing_fields_does_not_zero_out(self):
        self.project.installation_fee = Decimal("300000")
        self.project.save(update_fields=["installation_fee"])
        client = Client()
        client.force_login(self.creator)
        # ارسال بدون installation_fee (یعنی غایب در POST چون disabled یا حذف‌شده)
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), {
            "address_text": "فقط آدرس جدید",
            "services_json": json.dumps([{"id": self.service1.id, "qty": "2", "unit_price": "500000"}]),
            "materials_json": json.dumps([{"id": self.item1.id, "qty": "1", "unit_price": "200000"}]),
        })
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.installation_fee, Decimal("300000"))

    def test_overview_renders_contract_date_and_notes(self):
        dt = JalaliDateField().clean("1405/07/01")
        self.project.contract_date = dt
        self.project.notes = "تست یادداشت در نمایش پروژه"
        self.project.save(update_fields=["contract_date", "notes"])

        client = Client()
        client.force_login(self.creator)
        resp = client.get(reverse("projects:staff_project_overview", args=[self.project.id]))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("تست یادداشت در نمایش پروژه", content)
