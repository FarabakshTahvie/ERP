import json
from datetime import date
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from projects.models import Project, WorkflowTemplate, WorkflowStepTemplate
from projects.services import create_project_from_technician_intake
from projects.workflow_v3 import build_workflow_v3
from finance.models import Invoice
from notifications.models import NotificationPolicy


class NewProjectIntakeTests(TestCase):
    def setUp(self):
        self.tech = User.objects.create_user(
            username="tech_intake", phone_number="09120000091",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.tech.specialties.add(self.sp_reception)

        self.template = WorkflowTemplate.objects.create(name="قالب پیش‌فرض", is_default=True)
        WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="صدور پیش‌فاکتور",
        )
        self.service = Service.objects.create(name="سرویس تست")
        self.item = Item.objects.create(name="متریال تست")

        NotificationPolicy.objects.get_or_create(
            notification_type="invoice_issued",
            defaults={"channel_policy": "sms_only", "fallback_after_minutes": 15},
        )

    def test_new_project_form_render(self):
        client = Client()
        client.force_login(self.tech)
        resp = client.get(reverse("projects:new_project_form"))
        self.assertEqual(resp.status_code, 200)

    def test_party_search_found_and_not_found(self):
        party = Party.objects.create(name="شرکت همکار", phone_number="09120000092", is_partner=True)
        client = Client()
        client.force_login(self.tech)

        r1 = client.get(reverse("projects:new_project_party_search") + "?phone_number=09120000092")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("شرکت همکار", r1.content.decode("utf-8"))

        r2 = client.get(reverse("projects:new_project_party_search") + "?phone_number=09129999999")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("طرف‌حسابی با این شماره پیدا نشد", r2.content.decode("utf-8"))

    @mock.patch("notifications.services.SMSService.send_invoice_issued")
    def test_submit_new_project_creates_project_invoice_and_notifies(self, mock_sms):
        from projects.workflow_v3 import build_workflow_v3
        build_workflow_v3(make_default=True)
        mock_sms.return_value = {"success": True, "message_id": "1001"}
        client = Client()
        client.force_login(self.tech)

        post_data = {
            "project_name": "پروژه‌ی مشتری جدید",
            "phone_number": "09120000093",
            "party_name": "مشتری جدید تست",
            "entity_type": "individual",
            "roles": ["client"],
            "latitude": "35.689200",
            "longitude": "51.389000",
            "address_text": "تهران خیابان تست",
            "visit_date": "1405/07/20",
        }
        resp = client.post(reverse("projects:new_project_submit"), post_data)
        self.assertRedirects(resp, reverse("home"))

        project = Project.objects.get(name="پروژه‌ی مشتری جدید")
        self.assertEqual(project.owner.phone_number, "09120000093")
        self.assertIsNotNone(project.location)
        self.assertIsNotNone(project.visit_date)
        self.assertFalse(hasattr(project, "invoice"))
        mock_sms.assert_not_called()


class PartySearchForPurchaseTests(TestCase):
    """جستجوی طرف‌حساب از فرم ثبت خرید انبار (اصلاح روی W2)."""

    def setUp(self):
        self.sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")
        self.warehouse_user = User.objects.create_user(
            username="pw_wh_user", phone_number="09370000001",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        self.warehouse_user.specialties.add(self.sp_warehouse)

        self.plain_tech = User.objects.create_user(
            username="pw_plain_tech", phone_number="09370000002",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )

    def test_warehouse_keeper_without_reception_can_search_parties(self):
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(reverse("projects:new_project_party_search") + "?phone_number=09370000099")
        self.assertEqual(resp.status_code, 200)

    def test_plain_employee_without_any_relevant_specialty_denied(self):
        client = Client()
        client.force_login(self.plain_tech)
        resp = client.get(reverse("projects:new_project_party_search") + "?phone_number=09370000099")
        self.assertEqual(resp.status_code, 302)

    def test_supplier_context_shows_existing_role_badges_and_auto_add_hint(self):
        party = Party.objects.create(
            name="کارفرمای موجود برای خرید", phone_number="09370000003",
            entity_type=Party.EntityType.INDIVIDUAL, national_code="5555555555", is_client=True,
        )
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(
            reverse("projects:new_project_party_search")
            + f"?phone_number={party.phone_number}&prefix=supplier_&context_role=supplier"
        )
        content = resp.content.decode("utf-8")
        self.assertIn("کارفرما", content)
        self.assertIn("نقش «تأمین‌کننده» را نداشت", content)

    def test_supplier_context_hides_hint_when_already_supplier(self):
        party = Party.objects.create(
            name="تامین‌کننده‌ی از قبل", phone_number="09370000004",
            entity_type=Party.EntityType.INDIVIDUAL, national_code="6666666666", is_supplier=True,
        )
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(
            reverse("projects:new_project_party_search")
            + f"?phone_number={party.phone_number}&prefix=supplier_&context_role=supplier"
        )
        content = resp.content.decode("utf-8")
        self.assertIn("تأمین‌کننده", content)
        self.assertNotIn("نقش «تأمین‌کننده» را نداشت", content)

    def test_owner_search_still_hides_role_badges_without_context_role(self):
        """رگرسیون: فرم صاحب ملک در ثبت پروژه نباید تحت تاثیر این اصلاح قرار بگیرد."""
        party = Party.objects.create(
            name="طرف‌حساب چندنقشی", phone_number="09370000005",
            entity_type=Party.EntityType.INDIVIDUAL, national_code="7777777777",
            is_client=True, is_partner=True,
        )
        client = Client()
        client.force_login(self.warehouse_user)
        resp = client.get(
            reverse("projects:new_project_party_search")
            + f"?phone_number={party.phone_number}&prefix=owner_"
        )
        content = resp.content.decode("utf-8")
        self.assertNotIn("کارفرما", content)
        self.assertNotIn("شریک تجاری", content)


class ProjectNameFieldTests(TestCase):
    def setUp(self):
        from projects.workflow_v3 import build_workflow_v3
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        self.tech = User.objects.create_user(username="pn_tech", phone_number="09120000191", password="pw",
                                             role=User.Role.EMPLOYEE)
        self.tech.specialties.add(Specialty.objects.get_or_create(name="پذیرش")[0])
        self.party = Party.objects.create(name="مشتری نام‌پروژه", phone_number="09120000192", is_client=True)
        self.web = Client()
        self.web.force_login(self.tech)
        self.url = reverse("projects:new_project_submit")

    def post(self, **extra):
        data = {"party_id": self.party.id, "visit_date": "1405/07/20"}
        data.update(extra)
        return self.web.post(self.url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_form_has_required_project_name_field(self):
        html = self.web.get(reverse("projects:new_project_form")).content.decode("utf-8")
        self.assertRegex(html, r'<input[^>]*name="project_name"[^>]*required')

    def test_missing_or_blank_name_is_rejected_on_server(self):
        for extra in ({}, {"project_name": ""}, {"project_name": "   "}):
            resp = self.post(**extra)
            self.assertFalse(resp.json()["ok"])
            self.assertIn("نام پروژه", resp.json()["error"])
        self.assertEqual(Project.objects.count(), 0)

    def test_typed_name_is_used_and_whitespace_normalized(self):
        resp = self.post(project_name="  برج    نگین  ")
        self.assertTrue(resp.json()["ok"])
        self.assertEqual(Project.objects.get().name, "برج نگین")

    def test_too_long_name_is_rejected(self):
        resp = self.post(project_name="الف" * 256)
        self.assertFalse(resp.json()["ok"])
        self.assertEqual(Project.objects.count(), 0)

    def test_service_without_name_keeps_old_behaviour(self):
        project, _, _ = create_project_from_technician_intake(
            created_by=self.tech, party_id=self.party.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.assertEqual(project.name, self.party.name)

    def test_service_blank_name_raises(self):
        with self.assertRaises(ValueError):
            create_project_from_technician_intake(
                created_by=self.tech, party_id=self.party.id, visit_date=date(2026, 10, 11),
                issue_proforma=False, project_name="   ")

