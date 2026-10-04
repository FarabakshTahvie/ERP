from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from finance.admin import PaymentInline
from finance.models import Invoice

User = get_user_model()


class MockRequest:
    pass


class AdminPaymentInlineGuardTests(TestCase):
    def test_payment_inline_permissions_are_false(self):
        site = AdminSite()
        inline = PaymentInline(Invoice, site)
        request = MockRequest()
        self.assertFalse(inline.has_add_permission(request))
        self.assertFalse(inline.has_change_permission(request))
        self.assertFalse(inline.has_delete_permission(request))
