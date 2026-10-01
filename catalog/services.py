from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from .models import MarginRule

_SCOPE_RANK = {MarginRule.Scope.ITEM: 3, MarginRule.Scope.CATEGORY: 2, MarginRule.Scope.GLOBAL: 1}


def _active_percent_rules(at):
    return list(
        MarginRule.objects.filter(value_type=MarginRule.ValueType.PERCENT, valid_from__lte=at)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=at))
    )


def resolve_margin_percents(items, at=None):
    """{item_id: درصد سود}. اولویت: کالا > دسته > سراسری؛ بعد priority؛ بعد جدیدترین valid_from. بدون قانون = ۰."""
    rules = _active_percent_rules(at or timezone.now())
    out = {}
    for item in items:
        best = None
        for r in rules:
            if r.scope == MarginRule.Scope.ITEM and r.item_id != item.pk:
                continue
            if r.scope == MarginRule.Scope.CATEGORY and (r.category_id is None or r.category_id != item.category_id):
                continue
            key = (_SCOPE_RANK[r.scope], r.priority, r.valid_from)
            if best is None or key > best[0]:
                best = (key, r)
        out[item.pk] = Decimal(best[1].value) if best else Decimal("0")
    return out


def has_global_margin(at=None):
    return any(r.scope == MarginRule.Scope.GLOBAL for r in _active_percent_rules(at or timezone.now()))
