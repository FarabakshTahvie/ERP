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



    def test_plain_employee_without_any_relevant_specialty_denied(self):
        client = Client()
        client.force_login(self.plain_tech)
        resp = client.get(reverse("projects:new_project_party_search") + "?phone_number=09370000099")
        self.assertEqual(resp.status_code, 302)




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

    def test_missing_or_blank_name_is_rejected_on_server(self):
        for extra in ({}, {"project_name": ""}, {"project_name": "   "}):
            resp = self.post(**extra)
            self.assertFalse(resp.json()["ok"])
            self.assertIn("نام پروژه", resp.json()["error"])
        self.assertEqual(Project.objects.count(), 0)



