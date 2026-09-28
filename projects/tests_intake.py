import json
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from projects.models import Project, WorkflowTemplate, WorkflowStepTemplate
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

    @mock.patch("notifications.services.SMSService.send_otp")
    def test_submit_new_project_creates_project_invoice_and_notifies(self, mock_sms):
        mock_sms.return_value = {"success": True, "message_id": "1001"}
        client = Client()
        client.force_login(self.tech)

        post_data = {
            "phone_number": "09120000093",
            "party_name": "مشتری جدید تست",
            "entity_type": "individual",
            "roles": ["client"],
            "latitude": "35.689200",
            "longitude": "51.389000",
            "address_text": "تهران خیابان تست",
            "services_json": json.dumps([{"id": self.service.id, "qty": 2, "unit_price": 500000}]),
            "materials_json": json.dumps([{"id": self.item.id, "qty": 1, "unit_price": 200000}]),
            "send_sms": "on",
        }
        resp = client.post(reverse("projects:new_project_submit"), post_data)
        self.assertRedirects(resp, reverse("home"))

        project = Project.objects.get(name="مشتری جدید تست")
        self.assertEqual(project.owner.phone_number, "09120000093")
        self.assertIsNotNone(project.location)

        invoice = Invoice.objects.get(project=project)
        self.assertEqual(invoice.total_amount, 1200000)


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

