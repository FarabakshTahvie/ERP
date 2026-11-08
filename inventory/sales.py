import re
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.capabilities import can
from utils.utils import normalize_phone
from .models import Sale, SaleLine, StockMovement
from .services import assert_stockable, consume_stock, get_active_item, parse_decimal_input

BAD_LINES = "کالاهای فروش درست ارسال نشد؛ صفحه را دوباره باز کنید."
MAX_LINES = 50
MAX_QTY = Decimal("9999999")
MAX_PRICE = Decimal("1000000000000")
QTY_Q = Decimal("0.0001")
NAME_MAX = 150


def clean_customer(name, phone):
    name = " ".join(str(name or "").split())
    if len(name) > NAME_MAX:
        raise ValueError(f"نام مشتری نباید بیش از {NAME_MAX} نویسه باشد.")
    phone = normalize_phone(phone)
    if phone and not re.fullmatch(r"0\d{10}", phone):
        raise ValueError("شماره‌ی مشتری را ۱۱ رقمی بنویسید، مثل ۰۹۱۲۳۴۵۶۷۸۹.")
    return name, phone


def _clean_lines(raw_lines):
    if not isinstance(raw_lines, list) or not raw_lines:
        raise ValueError("حداقل یک کالا برای فروش بنویسید.")
    if len(raw_lines) > MAX_LINES:
        raise ValueError(f"در هر فروش حداکثر {MAX_LINES} کالا ثبت می‌شود.")
    lines = []
    for raw in raw_lines:
        if not isinstance(raw, dict):
            raise ValueError(BAD_LINES)
        item = get_active_item(raw.get("id"))
        assert_stockable(item)
        qty = parse_decimal_input(raw.get("qty"), label=f"مقدار «{item.name}»")
        price = parse_decimal_input(raw.get("unit_price"), label=f"قیمت فروش «{item.name}»")
        if qty > MAX_QTY or price >= MAX_PRICE:
            raise ValueError(f"مقدار یا قیمت «{item.name}» بیش از حد بزرگ است.")
        qty = qty.quantize(QTY_Q)
        if qty <= 0:
            raise ValueError(f"مقدار «{item.name}» خیلی کوچک است.")
        if price != price.to_integral_value():
            raise ValueError(f"قیمت «{item.name}» را به تومان و بدون اعشار بنویسید.")
        lines.append({"item": item, "qty": qty, "unit_price": price.to_integral_value()})
    return lines


@transaction.atomic
def create_sale(*, actor, lines_raw, customer_name="", customer_phone="", notes=""):
    """فروش کالا از انبار بیرون از پروژه. هر قلم همان لحظه به روش FIFO کم می‌شود (نوع حرکت «فروش»،
    وصل به همین فروش). موجودی کم باشد کل فروش ثبت نمی‌شود."""
    if not can(actor, "inventory.manage"):
        raise ValueError("فقط انباردار یا حسابدار می‌تواند فروش ثبت کند.")
    lines = _clean_lines(lines_raw)
    name, phone = clean_customer(customer_name, customer_phone)
    notes = " ".join(str(notes or "").split())
    if len(notes) > 255:
        raise ValueError("توضیح نباید بیش از ۲۵۵ نویسه باشد.")
    sale = Sale.objects.create(sold_at=timezone.now(), customer_name=name, customer_phone=phone,
                               notes=notes, created_by=actor)
    who = name or phone or "بدون نام"
    for line in lines:
        used = consume_stock(item=line["item"], qty=line["qty"], user=actor, related_object=sale,
                             notes=f"فروش به {who}"[:255], movement_type=StockMovement.MovementType.SALE)
        cost = sum((take * unit for _lot, take, unit in used), Decimal("0"))
        SaleLine.objects.create(sale=sale, item=line["item"], qty=line["qty"],
                                unit_price=line["unit_price"], cost_total=cost.quantize(Decimal("1")))
    return sale
