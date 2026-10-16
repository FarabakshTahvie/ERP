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
        from messenger.models import Conversation
        self.assertEqual(Conversation.objects.filter(is_main=True).count(), 1)
        self.assertEqual(Warehouse.objects.filter(is_default=True).count(), 1)
        self.assertEqual(Party.objects.filter(is_internal=True).count(), 1)
        self.assertEqual(NotificationPolicy.objects.count(), 9)
        tpl = WorkflowTemplate.objects.get(is_default=True)
        self.assertEqual((tpl.name, tpl.steps.count()), ("گردش‌کار v3", 11))
        self.assertTrue(Specialty.objects.filter(name__in=["حسابدار", "انباردار", "پذیرش"]).count() == 3)
        self.assertEqual(MarginRule.objects.count(), 0)

