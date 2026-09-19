from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Party
from catalog.models import Service, Item
from projects.models import Project, ProjectService, ProjectMaterial, ProjectParticipant
from finance.models import Invoice, InvoiceLine, Payment, LedgerEntry
from finance.services import generate_invoice_for_project, approve_payment

User = get_user_model()


class FinanceInvoiceTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(
            name="شریک تجاری نمونه",
            entity_type=Party.EntityType.COMPANY,
            company_registration_number="554433",
            is_partner=True,
        )
        self.contractor_party = Party.objects.create(
            name="پیمانکار کانال‌ساز",
            entity_type=Party.EntityType.INDIVIDUAL,
            national_code="1234567890",
            is_contractor=True,
        )
        self.user = User.objects.create_user(username="finance_admin", password="password123", role=User.Role.ADMIN)

        self.service = Service.objects.create(name="کانال‌کشی گالوانیزه")
        self.item = Item.objects.create(
            name="دریچه خطی آلومینیومی",
            item_type=Item.ItemType.PART,
            unit=Item.Unit.PIECE,
            moving_average_cost=Decimal('250000'),
        )

        self.project = Project.objects.create(
            name="پروژه اداری پارس",
            partner=self.partner,
            installation_fee=Decimal('5000000'),
            shipping_fee=Decimal('1000000'),
            extra_fee=Decimal('500000'),
            created_by=self.user,
        )
        ProjectService.objects.create(project=self.project, service=self.service, qty=100, unit_price=Decimal('80000'))
        ProjectMaterial.objects.create(project=self.project, item=self.item, qty=10, unit_price=Decimal('350000'))
        ProjectParticipant.objects.create(
            project=self.project,
            party=self.contractor_party,
            role=ProjectParticipant.ParticipantRole.CONTRACTOR,
            agreed_cost=Decimal('2000000'),
        )

    def test_generate_invoice_snapshots_and_totals(self):
        # محاسبات:
        # خدمات: 100 * 80,000 = 8,000,000
        # متریال: 10 * 350,000 = 3,500,000
        # نصب: 5,000,000
        # ارسال: 1,000,000
        # مازاد (شامل هزینه پیمانکار 2M + مازاد دستی 500k): 2,500,000
        # جمع کل: 20,000,000 تومان
        invoice = generate_invoice_for_project(self.project)
        self.assertEqual(invoice.total_amount, Decimal('20000000'))
        self.assertEqual(invoice.paid_amount, Decimal('0'))
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)

        # بررسی اسنپ‌شات ردیف‌ها
        lines = invoice.lines.all()
        self.assertEqual(lines.count(), 5)

        material_line = lines.get(line_type=InvoiceLine.LineType.MATERIAL)
        self.assertEqual(material_line.cost_snapshot, Decimal('250000'))

    def test_payment_methods_and_credit_ledger(self):
        invoice = generate_invoice_for_project(self.project)

        # پرداخت اول: درگاه پرداخت ۱۰ میلیون تومان -> خودکار APPROVED می‌شود
        pay1 = Payment.objects.create(
            invoice=invoice,
            method=Payment.Method.GATEWAY,
            amount=Decimal('10000000'),
            reference_number="TXN-123456",
        )
        invoice.refresh_from_db()
        self.assertEqual(pay1.status, Payment.Status.APPROVED)
        self.assertEqual(invoice.paid_amount, Decimal('10000000'))
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)

        # پرداخت دوم: اعتباری ۱۰ میلیون تومان -> PENDING
        pay2 = Payment.objects.create(
            invoice=invoice,
            method=Payment.Method.CREDIT,
            amount=Decimal('10000000'),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('10000000'))  # چون هنوز تایید نشده

        # تایید پرداخت اعتباری توسط مدیر
        approve_payment(pay2, approved_by=self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('20000000'))
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(invoice.settled_at)

        # بررسی سند دفتر حساب (LedgerEntry) برای پرداخت اعتباری
        ledger = LedgerEntry.objects.filter(party=self.partner, entry_type=LedgerEntry.EntryType.DEBIT).first()
        self.assertIsNotNone(ledger)
        self.assertEqual(ledger.amount, Decimal('10000000'))
        self.assertEqual(self.partner.balance, Decimal('10000000'))
