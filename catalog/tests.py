from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from catalog.models import Item, ItemCategory, MarginRule
from catalog.services import resolve_margin_percents, has_global_margin


class MarginServiceTests(TestCase):
    def setUp(self):
        self.cat1 = ItemCategory.objects.create(name="دسته ۱")
        self.item1 = Item.objects.create(name="کالا ۱", category=self.cat1)
        self.item2 = Item.objects.create(name="کالا ۲")

    def test_margin_priority_and_hierarchy(self):
        now = timezone.now()
        # Global: 10%
        MarginRule.objects.create(
            scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("10"), valid_from=now - timezone.timedelta(days=1),
        )
        # Category: 15%
        MarginRule.objects.create(
            scope=MarginRule.Scope.CATEGORY, category=self.cat1,
            value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("15"), valid_from=now - timezone.timedelta(days=1),
        )
        # Item: 25%
        MarginRule.objects.create(
            scope=MarginRule.Scope.ITEM, item=self.item1,
            value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("25"), valid_from=now - timezone.timedelta(days=1),
        )

        res = resolve_margin_percents([self.item1, self.item2], at=now)
        self.assertEqual(res[self.item1.pk], Decimal("25"))  # Item scope wins
        self.assertEqual(res[self.item2.pk], Decimal("10"))  # Global applies

    def test_expired_or_future_margin_ignored(self):
        now = timezone.now()
        MarginRule.objects.create(
            scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("30"),
            valid_from=now + timezone.timedelta(days=1),  # Future
        )
        MarginRule.objects.create(
            scope=MarginRule.Scope.GLOBAL, value_type=MarginRule.ValueType.PERCENT,
            value=Decimal("40"),
            valid_from=now - timezone.timedelta(days=5),
            valid_to=now - timezone.timedelta(days=1),  # Expired
        )
        self.assertFalse(has_global_margin(now))
        res = resolve_margin_percents([self.item1], at=now)
        self.assertEqual(res[self.item1.pk], Decimal("0"))
