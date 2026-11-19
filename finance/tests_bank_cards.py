from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.models import Party
from finance.bank_cards import is_valid_card, is_valid_sheba, normalize_card, normalize_sheba
from finance.models import BankCard, Invoice
from projects.models import Project
from utils.test_helpers import make_accountant

CARD1, CARD2, CARD3 = "6037991234567893", "6104337812345674", "6219861234567898"
SHEBA = "IR850123456789012345678901"


def make_card(**kw):
    data = dict(bank="melli", holder_name="شرکت فرابخش", card_number=CARD1, sheba=SHEBA)
    data.update(kw)
    return BankCard.objects.create(**data)


class BankCardValidationTests(SimpleTestCase):
    def test_luhn_accepts_real_numbers_and_rejects_the_rest(self):
        self.assertTrue(is_valid_card(CARD1) and is_valid_card(CARD2) and is_valid_card(CARD3))
        for bad in ("6037991234567894", "603799123456789", "0000000000000000", "abcd", ""):
            self.assertFalse(is_valid_card(bad), bad)

    def test_sheba_check_digits(self):
        self.assertTrue(is_valid_sheba(SHEBA))
        for bad in ("IR860123456789012345678901", "IR85012345678901234567890",
                    "XX850123456789012345678901", ""):
            self.assertFalse(is_valid_sheba(bad), bad)


class BankCardModelTests(TestCase):
    def test_duplicate_card_number_is_refused_even_when_typed_with_spaces(self):
        make_card()
        with self.assertRaises(ValidationError):
            BankCard(bank="mellat", holder_name="y", card_number="6037 9912 3456 7893").full_clean()


class BankCardAdminTests(TestCase):
    def test_only_the_manager_reaches_the_admin_pages(self):
        su = User.objects.create_superuser(username="bc_su", password="pw")
        staff = make_accountant("bc_acc")
        staff.is_staff = True
        staff.save()
        url = reverse("admin:finance_bankcard_changelist")
        c = Client()
        c.force_login(su)
        self.assertEqual(c.get(url).status_code, 200)
        c.force_login(staff)
        self.assertEqual(c.get(url).status_code, 403)


class BankCardSourceGuardTests(SimpleTestCase):
    BASE = Path(settings.BASE_DIR)

    def test_bank_cards_js_has_no_unsafe_html_sinks(self):
        text = (self.BASE / "static" / "js" / "bank_cards.js").read_text(encoding="utf-8")
        for word in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(word, text, word)

    def test_bank_cards_js_is_registered_for_tailwind(self):
        css = (self.BASE / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn('@source "../js/bank_cards.js";', css)


class BankCardCategoryTests(TestCase):
    def setUp(self):
        self.accountant = make_accountant("bcc_acc")
        self.tech = User.objects.create_user(username="bcc_tech", password="pw", role=User.Role.EMPLOYEE)

    def test_default_category_is_farabakhsh_and_invalid_rejected(self):
        c1 = make_card()
        self.assertEqual(c1.category, BankCard.Category.FARABAKHSH)

        from finance.services import create_bank_card, update_bank_card
        c2 = create_bank_card(actor=self.accountant, bank="mellat", holder_name="کارت نیرو",
                              card_number=CARD2, category=BankCard.Category.STAFF)
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        for bad in ("", "unknown", "other"):
            with self.assertRaises(ValueError):
                create_bank_card(actor=self.accountant, bank="saman", holder_name="نامعتبر",
                                 card_number=CARD3, category=bad)
        self.assertFalse(BankCard.objects.filter(card_number=CARD3).exists())

        with self.assertRaises(ValueError):
            update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                             holder_name="کارت نیرو", card_number=CARD2, category="bad")
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                         holder_name="کارت نیرو ویرایش", card_number=CARD2)
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                         holder_name="کارت نیرو ویرایش", card_number=CARD2,
                         category=BankCard.Category.FARABAKHSH)
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.FARABAKHSH)


class BankCardViewCategoryTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="bcv_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("bcv_acc")
        self.tech = User.objects.create_user(username="bcv_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری کارت", is_client=True, phone_number="09128889900")
        self.customer = User.objects.create_user(username="bcv_cli", password="pw", role=User.Role.CLIENT, party=self.party)
        self.company_card = make_card(holder_name="کارت شرکت فرابخش", card_number=CARD1,
                                      cvv2="321", expiry="06/05", category=BankCard.Category.FARABAKHSH)
        self.staff_card = make_card(bank="mellat", holder_name="کارت نیروی فنی", card_number=CARD2,
                                    sheba="", cvv2="999", expiry="07/08", category=BankCard.Category.STAFF)

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_staff_cards_never_appear_in_customer_payment_forms(self):
        from projects.models import ProjectStage, StageApproval, WorkflowStepTemplate, WorkflowTemplate
        tpl = WorkflowTemplate.objects.create(name="قالب کارت پرداخت")
        step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="تایید پیش‌فاکتور",
                                                 requires_payment_selection=True)
        project = Project.objects.create(name="پروژه کارت", partner=self.party, owner=self.party,
                                         workflow_template=tpl, status=Project.Status.IN_PROGRESS)
        invoice = Invoice.objects.create(project=project, number="INV-BC-1", billed_party=self.party,
                                         total_amount=Decimal("500000"), issue_date=timezone.localdate(),
                                         status=Invoice.Status.SENT)
        stage = ProjectStage.objects.create(project=project, step_template=step, order=1,
                                            title="تایید پیش‌فاکتور", status=ProjectStage.Status.WAITING_APPROVAL)
        approval = StageApproval.objects.create(stage=stage, sent_to_party=self.party)

        c = self.login(self.customer)
        for url in (reverse("finance:portal_add_payment", args=[invoice.uuid]),
                    reverse("projects:portal_stage_approval", args=[approval.id])):
            resp = c.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertContains(resp, "کارت شرکت فرابخش")
            self.assertNotContains(resp, "کارت نیروی فنی")
            self.assertNotContains(resp, CARD2)

    def test_tabs_isolation_and_permissions_on_bank_cards_page(self):
        url = reverse("finance:bank_cards")
        for user in (self.manager, self.accountant):
            c = self.login(user)
            r_company = c.get(url)
            self.assertEqual(r_company.status_code, 200)
            self.assertContains(r_company, "کارت شرکت فرابخش")
            self.assertNotContains(r_company, "کارت نیروی فنی")
            self.assertContains(r_company, "?tab=staff")

            r_staff = c.get(url + "?tab=staff")
            self.assertEqual(r_staff.status_code, 200)
            self.assertContains(r_staff, "کارت نیروی فنی")
            self.assertContains(r_staff, "999")
            self.assertNotContains(r_staff, "کارت شرکت فرابخش")

        for user in (self.tech, self.customer):
            c = self.login(user)
            r = c.get(url + "?tab=staff")
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "کارت شرکت فرابخش")
            self.assertNotContains(r, "کارت نیروی فنی")
            self.assertNotContains(r, "?tab=staff")
            self.assertNotContains(r, "321")

    def test_create_and_move_category_via_views(self):
        c = self.login(self.accountant)
        r_bad = c.post(reverse("finance:bank_card_create"), {
            "category": "wrong", "bank": "saman", "holder_name": "تست", "card_number": CARD3,
        })
        self.assertEqual(r_bad.status_code, 400)

        r_ok = c.post(reverse("finance:bank_card_create"), {
            "category": "staff", "bank": "saman", "holder_name": "نیروی جدید", "card_number": CARD3,
        })
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.json(), {"ok": True, "category": "staff"})
        created = BankCard.objects.get(card_number=CARD3)
        self.assertEqual(created.category, BankCard.Category.STAFF)

        r_move = c.post(reverse("finance:bank_card_update", args=[created.id]), {
            "category": "farabakhsh", "bank": "saman", "holder_name": "نیروی جدید", "card_number": CARD3,
        })
        self.assertEqual(r_move.status_code, 200)
        self.assertEqual(r_move.json(), {"ok": True, "category": "farabakhsh"})
        created.refresh_from_db()
        self.assertEqual(created.category, BankCard.Category.FARABAKHSH)

        for outsider in (self.tech, self.customer):
            oc = self.login(outsider)
            self.assertEqual(oc.post(reverse("finance:bank_card_create"), {
                "category": "staff", "bank": "saman", "holder_name": "x", "card_number": "6037991234567885",
            }).status_code, 404)

    def test_admin_includes_category(self):
        from finance.admin import BankCardAdmin
        self.assertIn("category", BankCardAdmin.list_display)
        self.assertIn("category", BankCardAdmin.list_filter)
        self.assertIn("category", BankCardAdmin.fields)
