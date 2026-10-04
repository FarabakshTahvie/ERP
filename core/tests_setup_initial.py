from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalog.models import MarginRule
from core.models import Party, Specialty
from inventory.models import Warehouse
from notifications.models import NotificationPolicy
from projects.models import WorkflowTemplate


def run(**kw):
    call_command("setup_initial_data", stdout=StringIO(), **kw)


class SetupInitialDataTests(TestCase):
    def test_creates_everything_and_is_idempotent(self):
        run(); run()
        self.assertEqual(Warehouse.objects.filter(is_default=True).count(), 1)
        self.assertEqual(Party.objects.filter(is_internal=True).count(), 1)
        self.assertEqual(NotificationPolicy.objects.count(), 7)
        tpl = WorkflowTemplate.objects.get(is_default=True)
        self.assertEqual((tpl.name, tpl.steps.count()), ("گردش‌کار v2", 12))
        self.assertTrue(Specialty.objects.filter(name__in=["حسابدار", "انباردار", "پذیرش"]).count() == 3)
        self.assertEqual(MarginRule.objects.count(), 0)

    def test_margin_created_once_and_validated(self):
        run(margin="15"); run(margin="20")
        rules = MarginRule.objects.all()
        self.assertEqual((rules.count(), int(rules[0].value)), (1, 15))
        with self.assertRaises(CommandError):
            run(margin="abc")
        with self.assertRaises(CommandError):
            run(margin="900")

    def test_existing_default_warehouse_is_untouched(self):
        Warehouse.objects.create(name="انبار قدیمی", is_default=True)
        run()
        self.assertEqual(list(Warehouse.objects.values_list("name", flat=True)), ["انبار قدیمی"])
