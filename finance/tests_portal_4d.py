from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance.aging import debt_invoices, get_customer_aging_data
from finance.models import Invoice, Payment
from projects.models import Project
from utils.test_helpers import confirm_invoice


class StatementBase(TestCase):
    def setUp(self):
        self.a = Party.objects.create(name="مشتری الف", is_client=True, phone_number="09126663001")
        self.b = Party.objects.create(name="مشتری ب", is_client=True, phone_number="09126663002")
        self.ua = User.objects.create_user(username="st_a", password="pw", role=User.Role.CLIENT, party=self.a)
        self.ub = User.objects.create_user(username="st_b", password="pw", role=User.Role.CLIENT, party=self.b)
        self.today = timezone.localdate()

    def invoice(self, party, number, total="1000", confirmed=True, **kw):
        proj = Project.objects.create(name=f"پروژه {number}", partner=party, owner=party,
                                      status=Project.Status.IN_PROGRESS)
        inv = Invoice.objects.create(project=proj, number=number, billed_party=party, total_amount=Decimal(total),
                                     issue_date=self.today - timedelta(days=40), status=Invoice.Status.SENT, **kw)
        if confirmed:
            confirm_invoice(inv)
        return inv


class DebtDefinitionTests(StatementBase):
    def test_unconfirmed_is_not_debt_but_paid_or_confirmed_is(self):
        un = self.invoice(self.a, "INV-S-1", confirmed=False)
        ok = self.invoice(self.a, "INV-S-2")
        part = self.invoice(self.a, "INV-S-3", confirmed=False, paid_amount=Decimal("100"))
        ids = set(debt_invoices(self.a.invoices.all()).values_list("pk", flat=True))
        self.assertEqual(ids, {ok.pk, part.pk})
        self.assertNotIn(un.pk, ids)
        self.assertEqual(self.a.total_outstanding, Decimal("1000") + Decimal("900"))

    def test_aging_uses_only_debt_invoices(self):
        self.invoice(self.a, "INV-S-4", confirmed=False)
        summary, rows = get_customer_aging_data(self.a)
        self.assertEqual((rows, summary["total_outstanding"]), ([], 0))
        self.invoice(self.a, "INV-S-5")
        summary, rows = get_customer_aging_data(self.a)
        self.assertEqual(summary["days_31_60"], Decimal("1000"))
        self.assertEqual(summary["overdue"], Decimal("1000"))


class StatementViewTests(StatementBase):
    def test_own_data_only_and_unconfirmed_listed_as_waiting(self):
        self.invoice(self.a, "INV-S-6")
        self.invoice(self.a, "INV-S-7", confirmed=False)
        self.invoice(self.b, "INV-S-8")
        c = Client(); c.force_login(self.ua)
        resp = c.get(reverse("finance:portal_statement"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([i.number for i in resp.context["debts"]], ["INV-S-6"])
        self.assertEqual([i.number for i in resp.context["waiting"]], ["INV-S-7"])
        self.assertNotContains(resp, "INV-S-8".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))

    def test_pending_payment_does_not_reduce_balance_and_credit_is_informational(self):
        inv = self.invoice(self.a, "INV-S-9")
        Payment.objects.create(invoice=inv, method=Payment.Method.CARD_TO_CARD, amount=300, claimed_amount=300,
                               reference_number="R")
        Payment.objects.create(invoice=inv, method=Payment.Method.CREDIT, amount=500, claimed_amount=500,
                               status=Payment.Status.APPROVED, note="x")
        c = Client(); c.force_login(self.ua)
        resp = c.get(reverse("finance:portal_statement"))
        self.assertEqual(resp.context["summary"]["total_outstanding"], Decimal("1000"))
        self.assertEqual(resp.context["pending_total"], Decimal("300"))

    def test_user_without_party_gets_404_and_anonymous_redirects(self):
        staff = User.objects.create_user(username="st_staff", password="pw", role=User.Role.EMPLOYEE)
        c = Client(); c.force_login(staff)
        self.assertEqual(c.get(reverse("finance:portal_statement")).status_code, 404)
        c.logout()
        self.assertEqual(c.get(reverse("finance:portal_statement")).status_code, 302)
