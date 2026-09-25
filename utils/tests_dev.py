from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

User = get_user_model()


class DevTestPagesAccessTests(TestCase):
    def setUp(self):
        self.normal_user = User.objects.create_user(username="normal_dev_test", password="password123")
        self.superuser = User.objects.create_superuser(username="super_dev_test", password="password123")

    def test_normal_user_cannot_access(self):
        client = Client(SERVER_NAME='localhost')
        client.force_login(self.normal_user)
        for name in ["utils:dev_test_calendar", "utils:dev_test_map", "utils:dev_test_design_system"]:
            resp = client.get(reverse(name))
            self.assertNotEqual(resp.status_code, 200)

    def test_superuser_can_access(self):
        client = Client(SERVER_NAME='localhost')
        client.force_login(self.superuser)
        for name in ["utils:dev_test_calendar", "utils:dev_test_map", "utils:dev_test_design_system"]:
            resp = client.get(reverse(name))
            self.assertEqual(resp.status_code, 200)
