from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


class ResetStockDataTests(TestCase):
    def test_debug_guard_and_force(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("reset_stock_data", yes=True)
            call_command("reset_stock_data", yes=True, force=True)
