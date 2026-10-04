import jdatetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Specialty, Party
from catalog.models import Item
from inventory.models import Warehouse
from finance.models import Invoice
from projects.models import Project

User = get_user_model()


class CustomersCenterAndAgingTests(TestCase):
    def setUp(self):
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.accountant_user = User.objects.create_user(
            username="acc_cust", phone_number="09300000031",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        self.accountant_user.specialties.add(self.sp_accountant)

        self.partner = Party.objects.create(name="شریک", is_partner=True, entity_type=Party.EntityType.INDIVIDUAL, national_code="1111111111")
        self.client_party = Party.objects.create(name="مشتری سن بدهی", is_client=True, entity_type=Party.EntityType.INDIVIDUAL, national_code="2222222222")
        self.warehouse = Warehouse.objects.create(name="انبار", is_default=True)
        self.item = Item.objects.create(name="کالا", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)

        self.project = Project.objects.create(
            name="پروژه مشتری", partner=self.partner, owner=self.client_party, status=Project.Status.IN_PROGRESS
        )

        self.invoice = Invoice.objects.create(
            number="INV-AGING-01",
            billed_party=self.client_party, project=self.project, document_type=Invoice.DocumentType.FINAL,
            status=Invoice.Status.SENT, total_amount=1200000, issue_date=jdatetime.date(1405, 1, 15).togregorian()
        )
        from utils.test_helpers import confirm_invoice
        confirm_invoice(self.invoice)

    def test_customers_center_page_and_aging(self):
        self.client.force_login(self.accountant_user)
        
        response = self.client.get(reverse("finance:accounting_customers"), {
            "client_id": self.client_party.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "finance/accounting_customers.html")

        summary = response.context["aging_summary"]
        self.assertEqual(summary["total_outstanding"], Decimal("1200000"))
        self.assertGreater(summary["days_over_90"], 0)
