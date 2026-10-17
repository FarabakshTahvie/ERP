from django import template

from finance.bank_cards import logo_url
from finance.models import BankCard

register = template.Library()


@register.inclusion_tag("finance/partials/bank_cards_slider.html")
def bank_cards_slider():
    cards = list(BankCard.objects.filter(is_active=True))
    for c in cards:
        c.logo = logo_url(c.bank)
    return {"cards": cards}
