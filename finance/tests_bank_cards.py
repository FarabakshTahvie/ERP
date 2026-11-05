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
