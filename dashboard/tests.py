from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from dashboard import services
from finance import accounting
from finance.models import Invoice
from projects.models import (
    Project, ProjectStage, StageEvent, WorkflowStepTemplate, WorkflowTemplate,
)


class DashboardAccessTests(TestCase):
    def setUp(self):
        mk = User.objects.create_user
        self.manager = mk(username="d_m", password="pw", role=User.Role.ADMIN)
        self.accountant = mk(username="d_a", password="pw", role=User.Role.EMPLOYEE)
        self.tech = mk(username="d_t", password="pw", role=User.Role.EMPLOYEE)
        self.client_user = mk(username="d_c", password="pw", role=User.Role.CLIENT)

    def test_others_get_404_and_anonymous_redirects(self):
        c = Client()
        for user in (self.accountant, self.tech, self.client_user):
            c.force_login(user)
            self.assertEqual(c.get(reverse("dashboard:overview")).status_code, 404, user.username)
            self.assertEqual(c.get(reverse("dashboard:projects_table")).status_code, 404, user.username)
        c.logout()
        self.assertEqual(c.get(reverse("dashboard:overview")).status_code, 302)
