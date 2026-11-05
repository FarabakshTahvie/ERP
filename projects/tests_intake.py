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



