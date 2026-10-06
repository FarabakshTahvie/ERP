from decimal import Decimal
from django.utils import timezone
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party
from finance.models import Invoice
from projects.models import Project


class CustomersCenterSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(username="cmgr", role=User.Role.ADMIN, password="pw")
        cls.partner = Party.objects.create(name="شریک", is_partner=True)
        cls.party = Party.objects.create(name="مشتری دو فاکتوره", is_client=True)
        cls.proj1 = Project.objects.create(name="P1", partner=cls.partner, owner=cls.party)
        cls.proj2 = Project.objects.create(name="P2", partner=cls.partner, owner=cls.party)
        cls.inv1 = Invoice.objects.create(project=cls.proj1, billed_party=cls.party, number="INV1", issue_date=timezone.now().date(), total_amount=Decimal("1000"))
        cls.inv2 = Invoice.objects.create(project=cls.proj2, billed_party=cls.party, number="INV2", issue_date=timezone.now().date(), total_amount=Decimal("2000"))

    def test_customer_center_multiple_invoices_no_exception(self):
        c = Client()
        c.force_login(self.manager)
        url = reverse("finance:accounting_customers") + f"?client_id={self.party.pk}"
        res = c.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertIn("مشتری دو فاکتوره", res.content.decode("utf-8"))

    def test_invalid_client_id(self):
        c = Client()
        c.force_login(self.manager)
        self.assertEqual(c.get(reverse("finance:accounting_customers") + "?client_id=abc").status_code, 404)
        self.assertEqual(c.get(reverse("finance:accounting_customers") + f"?client_id=999999").status_code, 404)
