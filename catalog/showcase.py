import random
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Case, IntegerField, Value, When
from django.utils.safestring import mark_safe

from core.capabilities import can
from utils.jalali import to_fa_digits
from utils.markdown_lite import render_markdown
from utils.utils import separate_digits
from . import cache as catalog_cache
from . import media as catalog_media
from .models import Item, Service
from .services import resolve_margin_percents

PAGE_SIZE = 24
SLIDER_SIZE = 12
RELATED_SIZE = 6
RELATED_MIN_SAME = 4
NEGOTIABLE = "توافقی"
CALL_FOR_PRICE = "برای قیمت تماس بگیرید"


def scope_for(user):
    """«all»: مدیر، موارد مخفی را هم می‌بیند؛ «pub»: فقط روشن‌ها."""
    return "all" if can(user, "catalog.edit") else "pub"


def _qs(kind, scope):
    if kind == "service":
        qs = Service.objects.filter(is_active=True).exclude(children__isnull=False)   # فقط برگ
    else:
        qs = Item.objects.filter(is_active=True).select_related("category")
    if scope != "all":
        qs = qs.filter(show_to_clients=True)
    no_cover = Case(When(cover__gt="", then=Value(0)), default=Value(1), output_field=IntegerField())
    return qs.annotate(no_cover=no_cover).order_by("no_cover", "name", "pk")


def get_visible(kind, pk, scope):
    return _qs(kind, scope).filter(pk=pk).first()


def item_prices(items):
    """{id: (عدد قیمت، متن جایگزین)}. قیمت = میانگین موزون × (۱ + درصد قیمت‌گذاری)؛
    فقط وقتی هر دو مثبت‌اند، تا بهای خرید لو نرود."""
    margins = resolve_margin_percents(items)
    out = {}
    for it in items:
        cost, pct = Decimal(it.moving_average_cost or 0), margins.get(it.pk, Decimal("0"))
        if cost > 0 and pct > 0:
            price = (cost * (Decimal(100) + pct) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            out[it.pk] = (to_fa_digits(separate_digits(price)), "")
        else:
            out[it.pk] = ("", CALL_FOR_PRICE)
    return out


def _cards(kind, objs):
    objs = list(objs)
    prices = item_prices(objs) if kind == "item" else {}
    out = []
    for o in objs:
        num, note = prices.get(o.pk, ("", NEGOTIABLE))
        out.append({
            "kind": kind, "id": o.pk, "name": o.name, "route": f"catalog:{kind}_detail",
            "thumb": o.cover_thumb.url if o.cover_thumb else "",
            "price": num, "price_note": note,
            "unit": o.get_unit_display() if (kind == "item" and num) else "",
            "category": o.category.name if (kind == "item" and o.category_id) else "",
            "hidden": not o.show_to_clients,
        })
    return out


def list_page(kind, scope, page):
    """(کارت‌های این صفحه، صفحه‌ی بعد هست؟) کش‌شده."""
    def build():
        start = (page - 1) * PAGE_SIZE
        rows = list(_qs(kind, scope)[start:start + PAGE_SIZE + 1])
        return _cards(kind, rows[:PAGE_SIZE]), len(rows) > PAGE_SIZE
    return catalog_cache.remember(f"list:{kind}:{scope}:{page}", build)


def slider(kind, scope="pub"):
    return catalog_cache.remember(
        f"slider:{kind}:{scope}", lambda: _cards(kind, list(_qs(kind, scope)[:SLIDER_SIZE])))


def detail(kind, obj):
    """متن رندرشده، رسانه‌های بیرون از متن و قیمت. mark_safe فقط همین‌جاست و روی خروجی render_markdown (که اول escape می‌کند)."""
    def build():
        media = catalog_media.media_map(obj)
        text, used = render_markdown(obj.description, media)
        card = _cards(kind, [obj])[0]
        return {"html": text, "price": card["price"], "price_note": card["price_note"], "unit": card["unit"],
                "extra": [{"id": pk, **info} for pk, info in media.items() if pk not in used]}
    data = dict(catalog_cache.remember(f"detail:{kind}:{obj.pk}", build))
    data["html"] = mark_safe(data["html"])
    return data


def related(kind, obj, scope):
    """خدمات: رندوم. کالا: هم‌دسته؛ اگر کمتر از ۴ تا بود با رندوم پر می‌شود. حداکثر ۶ مورد، ۱۰ دقیقه در کش."""
    def build():
        base = _qs(kind, scope).exclude(pk=obj.pk)
        chosen = []
        if kind == "item" and obj.category_id:
            same = list(base.filter(category_id=obj.category_id).values_list("pk", flat=True))
            chosen = random.sample(same, min(len(same), RELATED_SIZE))
        if len(chosen) < RELATED_MIN_SAME:
            taken = set(chosen)
            rest = [pk for pk in base.values_list("pk", flat=True) if pk not in taken]
            chosen += random.sample(rest, min(len(rest), RELATED_SIZE - len(chosen)))
        by_id = {o.pk: o for o in _qs(kind, scope).filter(pk__in=chosen)}
        return _cards(kind, [by_id[pk] for pk in chosen if pk in by_id])
    return catalog_cache.remember(f"related:{kind}:{obj.pk}:{scope}", build)
