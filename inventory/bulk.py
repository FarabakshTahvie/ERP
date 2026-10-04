import json
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from catalog.models import Item
from .models import StockMovement, Warehouse
from .services import record_manual_stock_change, CHANGE_KIND_OPENING, CHANGE_KIND_ADJUST_INCREASE, CHANGE_KIND_ADJUST_DECREASE, get_active_item

MAX_BULK_ROWS = 50


def parse_bulk_json(raw_json):
    if not raw_json:
        raise ValueError("ردیفی برای ثبت نیست.")
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("فرمت داده‌ها نامعتبر است.")
    if not isinstance(data, list):
        raise ValueError("فرمت داده‌ها نامعتبر است.")
    if len(data) > MAX_BULK_ROWS:
        raise ValueError(f"حداکثر {MAX_BULK_ROWS} ردیف را می‌توان یک‌جا ثبت کرد.")
    return data


def validate_bulk_opening_lines(lines_data):
    seen_items = set()
    cleaned_lines = []
    for row in lines_data:
        item_id = row.get("item_id")
        qty_raw = str(row.get("qty") or "").strip()
        cost_raw = str(row.get("unit_cost") or "").strip()
        if not item_id or not qty_raw or not cost_raw:
            continue
        try:
            item = get_active_item(item_id)
        except Exception:
            raise ValueError("یکی از کالاها پیدا نشد؛ صفحه را دوباره باز کنید.")
        if item.id in seen_items:
            raise ValueError(f"کالای «{item.name}» تکرار شده است.")
        seen_items.add(item.id)
        cleaned_lines.append({"item": item, "qty_raw": qty_raw, "cost_raw": cost_raw})
    return cleaned_lines


@transaction.atomic
def commit_bulk_opening(lines_data, notes, user):
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("توضیح را بنویسید (مثلاً: موجودی اولیه‌ی انبار).")
    cleaned = validate_bulk_opening_lines(lines_data)
    if not cleaned:
        raise ValueError("ردیفی برای ثبت نیست.")
    for line in cleaned:
        record_manual_stock_change(
            item=line["item"],
            kind=CHANGE_KIND_OPENING,
            qty_raw=line["qty_raw"],
            notes=notes,
            user=user,
            unit_cost_raw=line["cost_raw"],
        )


def validate_bulk_reconciliation_lines(lines_data):
    seen_items = set()
    cleaned_lines = []
    for row in lines_data:
        item_id = row.get("item_id")
        qty_raw = str(row.get("qty") or "").strip()
        if not item_id or qty_raw == "":
            continue
        try:
            item = get_active_item(item_id)
        except Exception:
            raise ValueError("یکی از کالاها پیدا نشد؛ دوباره پیش‌نمایش بگیرید.")
        if item.id in seen_items:
            raise ValueError(f"کالای «{item.name}» تکرار شده است.")
        seen_items.add(item.id)
        try:
            qty = Decimal(qty_raw)
        except Exception:
            raise ValueError("ردیف شمارش‌شده‌ای نیست یا بیش از حد مجاز است.")
        if qty < 0:
            raise ValueError("ردیف شمارش‌شده‌ای نیست یا بیش از حد مجاز است.")
        diff = qty - item.current_stock
        if diff != 0:
            cleaned_lines.append({"item": item, "count_qty": qty, "diff": diff})
    return cleaned_lines


@transaction.atomic
def commit_bulk_reconciliation(lines_data, notes, user):
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("توضیح انبارگردانی را بنویسید.")
    cleaned = validate_bulk_reconciliation_lines(lines_data)
    if not cleaned:
        raise ValueError("هیچ اختلافی بین شمارش و موجودی سیستم پیدا نشد.")
    for line in cleaned:
        diff = line["diff"]
        kind = CHANGE_KIND_ADJUST_INCREASE if diff > 0 else CHANGE_KIND_ADJUST_DECREASE
        qty_raw = str(abs(diff))
        record_manual_stock_change(
            item=line["item"],
            kind=kind,
            qty_raw=qty_raw,
            notes=notes,
            user=user,
        )
