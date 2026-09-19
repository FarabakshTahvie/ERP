from django import template
from datetime import datetime, date
import jdatetime
from utils.utils import separate_digits, rial_to_toman, format_price

register = template.Library()


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    """
    Pagination Query Preserver:
    Preserves existing GET query parameters when navigating pages or applying filters.
    Example in template: <a href="?{% url_replace page=2 %}">صفحه ۲</a>
    """
    request = context.get('request')
    if not request:
        return ""

    query_params = request.GET.copy()
    for key, value in kwargs.items():
        query_params[key] = value

    return query_params.urlencode()


@register.filter
def get_item(dictionary, key):
    """
    Safely retrieves a dynamic key value from a dictionary in templates.
    Example in template: {{ my_dict|get_item:dynamic_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def to_jalali(value, format_str=None):
    """
    Converts Gregorian date or datetime to Jalali (Persian) date.
    - For datetime: Default format includes date and time without seconds (e.g., 1403/06/25 14:30).
    - For date: Default format includes date only (e.g., 1403/06/25).
    """
    if not value:
        return ""

    try:
        if isinstance(value, datetime):
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=value)
            if format_str:
                return jalali_dt.strftime(format_str)
            return jalali_dt.strftime("%Y/%m/%d %H:%M")
        elif isinstance(value, date):
            jalali_d = jdatetime.date.fromgregorian(date=value)
            if format_str:
                return jalali_d.strftime(format_str)
            return jalali_d.strftime("%Y/%m/%d")
    except Exception:
        return str(value)

    return str(value)


@register.filter
def intcomma_fa(value):
    """
    Separates numbers into 3-digit groups.
    Example: 1500000 -> 1,500,000
    """
    return separate_digits(value)


@register.filter
def to_toman(value, is_rial_input=True):
    """
    Converts Rials to Toman and formats with 3-digit comma separation.
    Example: 100000 -> 10,000 تومان
    """
    if value is None:
        return ""
    return format_price(value, currency="تومان", is_rial_input=is_rial_input)


@register.simple_tag
def icon(name, css_class="w-5 h-5"):
    """استفاده: {% icon "fan" "w-6 h-6 text-primary" %}"""
    from django.templatetags.static import static
    from django.utils.html import format_html
    return format_html('<svg class="{}"><use href="{}#{}"></use></svg>', css_class, static("icons/sprite.svg"), name)
