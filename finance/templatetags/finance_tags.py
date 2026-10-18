from django import template

from core.capabilities import can
from finance.bank_cards import logo_url
from finance.models import BankCard

register = template.Library()


@register.inclusion_tag("finance/partials/bank_cards_slider.html", takes_context=True)
def bank_cards_slider(context):
    """CVV2 و تاریخ انقضا فقط برای دارندگان bank_cards.manage؛ مشتری فقط شماره و شبا را می‌بیند."""
    user = getattr(context.get("request"), "user", None)
    show_secrets = bool(user is not None and user.is_authenticated and can(user, "bank_cards.manage"))
    cards = list(BankCard.objects.filter(is_active=True))
    for c in cards:
        c.logo = logo_url(c.bank)
    return {"cards": cards, "show_secrets": show_secrets}
