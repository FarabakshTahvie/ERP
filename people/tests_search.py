from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty


class PeopleSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="smgr", role=User.Role.ADMIN, password="pw")
        cls.intake = User.objects.create_user(username="sint", role=User.Role.EMPLOYEE, password="pw")
        cls.intake.specialties.add(Specialty.objects.get_or_create(name="پذیرش")[0])
        cls.warehouse = User.objects.create_user(username="swh", role=User.Role.EMPLOYEE, password="pw")
        cls.warehouse.specialties.add(Specialty.objects.get_or_create(name="انباردار")[0])

    def test_audience_search_permissions(self):
        c_intake = Client()
        c_intake.force_login(self.intake)
        self.assertEqual(c_intake.get(reverse("people:search") + "?kind=audience&q=test").status_code, 200)
        self.assertEqual(c_intake.get(reverse("people:search") + "?kind=parties&q=test").status_code, 404)

        c_wh = Client()
        c_wh.force_login(self.warehouse)
        self.assertEqual(c_wh.get(reverse("people:search") + "?kind=audience&q=test").status_code, 404)
