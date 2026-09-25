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
