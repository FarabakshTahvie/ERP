import csv
import hashlib
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse

from catalog.models import Item
from .services import (
    CHANGE_KIND_ADJUST_DECREASE, CHANGE_KIND_ADJUST_INCREASE, CHANGE_KIND_OPENING,
    _FA_TO_EN, normalize_item_name, record_manual_stock_change,
)

MAX_BULK_ROWS = 600
MAX_ERRORS_SHOWN = 50
PRICE_ABSOLUTE_LIMIT = Decimal("50000000")
PRICE_RATIO = Decimal("5")
MAX_QTY = Decimal("9999999")
MAX_COST = Decimal("1000000000000")
QTY_Q = Decimal("0.0001")
MODES = ("opening", "count")


def active_items_with_stock():
    return list(Item.objects.filter(is_active=True).annotate(
        stock_now=Coalesce(Sum("lots__qty_remaining"), Value(Decimal("0")),
                           output_field=DecimalField(max_digits=14, decimal_places=4))
    ).order_by("name"))


def _num(raw):
    text = str(raw or "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace("٫", ".").replace(" ", "")
    if not text or "e" in text.lower():
        raise InvalidOperation
    value = Decimal(text)
    if not value.is_finite():
        raise InvalidOperation
    return value


def _is_number(raw):
    try:
        _num(raw)
        return True
    except InvalidOperation:
        return False


def _fmt(value):
    return format(Decimal(value).normalize(), "f")


def content_digest(mode, text, notes):
    body = f"{mode}\n{(notes or '').strip()}\n{(text or '').replace(chr(13), '')}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _parse_rows(text):
    rows = []
    for number, line in enumerate((text or "").splitlines(), start=1):
        if line.strip():
            rows.append({"row": number, "cells": [c.strip() for c in line.split("\t")]})
    if rows:
        cells = rows[0]["cells"]
        if len(cells) > 1 and cells[1] != "" and not _is_number(cells[1]):
            rows = rows[1:]            # سطر عنوان ستون‌ها
    if len(rows) > MAX_BULK_ROWS:
        raise ValueError(f"حداکثر {MAX_BULK_ROWS} ردیف را می‌توان یک‌جا ثبت کرد.")
    if not rows:
        raise ValueError("چیزی برای ثبت وارد نشده است.")
    return rows


def _resolve(name, by_name, seen):
    key = normalize_item_name(name)
    found = by_name.get(key)
    if not found:
        return None, "کالایی با این نام پیدا نشد؛ نام باید با فهرست کالاها یکی باشد."
    if len(found) > 1:
        return None, "چند کالا با این نام هست؛ نام‌ها را در «کالای جدید» از هم جدا کنید."
    if found[0].pk in seen:
        return None, "این کالا در همین فهرست تکرار شده است."
    seen.add(found[0].pk)
    return found[0], None


def build_preview(mode, text):
    """پیش‌نمایش بدون هیچ نوشتنی. خطای ساختاری ValueError می‌دهد؛ خطای هر ردیف در errors می‌آید."""
    if mode not in MODES:
        raise ValueError("نوع ثبت نامعتبر است.")
    rows = _parse_rows(text)
    items = active_items_with_stock()
    by_name = {}
    for it in items:
        by_name.setdefault(normalize_item_name(it.name), []).append(it)

    lines, errors, seen = [], [], set()
    for r in rows:
        cells = r["cells"] + [""] * 3
        if mode == "opening" and cells[1] == "" and cells[2] == "":
            continue                      # ردیف پرنشده‌ی قالب
        item, err = _resolve(cells[0], by_name, seen)
        if err:
            errors.append({"row": r["row"], "text": f"«{cells[0]}»: {err}"})
            continue
        try:
            line = _opening_line(item, cells) if mode == "opening" else _count_line(item, cells)
        except ValueError as e:
            errors.append({"row": r["row"], "text": f"«{item.name}»: {e}"})
            continue
        if line:
            line["row"] = r["row"]
            lines.append(line)
    if not lines and not errors:
        raise ValueError("ردیف پرشده‌ای پیدا نشد؛ مقدار و بهای واحد را بنویسید."
                         if mode == "opening" else "هیچ اختلافی بین شمارش و موجودی سیستم پیدا نشد.")
    return {
        "mode": mode, "lines": lines, "errors": errors[:MAX_ERRORS_SHOWN], "error_count": len(errors),
        "warning_count": sum(1 for l in lines if l["warnings"]),
        "total_value": sum((l["value"] for l in lines), Decimal("0")) if mode == "opening" else None,
    }


def _opening_line(item, cells):
    try:
        qty, cost = _num(cells[1]), _num(cells[2])
    except InvalidOperation:
        raise ValueError("مقدار و بهای واحد باید عدد باشند.")
    if qty <= 0 or cost <= 0:
        raise ValueError("مقدار و بهای واحد باید بیشتر از صفر باشند.")
    if qty > MAX_QTY or cost > MAX_COST:
        raise ValueError("مقدار یا بها بیش از حد بزرگ است.")
    qty = qty.quantize(QTY_Q)
    warnings = []
    if item.stock_now > 0:
        warnings.append(f"از قبل موجودی دارد ({_fmt(item.stock_now)})؛ ثبت موجودی اولیه آن را اضافه می‌کند.")
    if cost > PRICE_ABSOLUTE_LIMIT:
        warnings.append("بهای واحد بیشتر از ۵۰ میلیون تومان است؛ شاید ریال نوشته‌اید.")
    avg = item.moving_average_cost
    if avg and avg > 0 and (cost >= avg * PRICE_RATIO or cost <= avg / PRICE_RATIO):
        warnings.append(f"بهای واحد با میانگین فعلی ({_fmt(avg)}) بیش از ۵ برابر فاصله دارد.")
    return {"item": item, "qty": qty, "cost": cost, "value": qty * cost, "warnings": warnings}


def _count_line(item, cells):
    if cells[1] == "":
        return None                    # شمارش نشده؛ نادیده گرفته می‌شود
    try:
        counted = _num(cells[1])
    except InvalidOperation:
        raise ValueError("مقدار شمارش‌شده باید عدد باشد.")
    if counted < 0 or counted > MAX_QTY:
        raise ValueError("مقدار شمارش‌شده نامعتبر است.")
    counted = counted.quantize(QTY_Q)
    stock = item.stock_now
    diff = (counted - stock).quantize(QTY_Q)
    if diff == 0:
        return None
    if diff > 0 and not (item.moving_average_cost and item.moving_average_cost > 0):
        raise ValueError("این کالا میانگین قیمتی ندارد؛ اضافه‌ی آن را از «ثبت مصرف یا تعدیل» با بها ثبت کنید.")
    warnings = []
    if counted == 0 and stock > 0:
        warnings.append("شمارش صفر برای کالایی که موجودی دارد.")
    if stock > 0 and diff > stock:
        warnings.append("شمارش بیش از دو برابر موجودی سیستم است.")
    return {"item": item, "stock": stock, "counted": counted, "diff": diff, "warnings": warnings}


@transaction.atomic
def commit(mode, text, notes, user, *, acknowledged):
    """همه‌چیز را دوباره از متن اعتبارسنجی می‌کند (به پیش‌نمایش اعتماد نمی‌شود)؛ یا همه ثبت می‌شود یا هیچ."""
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("توضیح سند را بنویسید.")
    preview = build_preview(mode, text)
    if preview["error_count"]:
        raise ValueError("ردیف‌های دارای خطا را اصلاح کنید.")
    if preview["warning_count"] and not acknowledged:
        raise ValueError("هشدارها را بخوانید و تیک «هشدارها را دیده‌ام» را بزنید.")
    label = "ورود گروهی موجودی اولیه" if mode == "opening" else "انبارگردانی"
    note = f"{label}: {notes}"[:255]
    for line in preview["lines"]:
        if mode == "opening":
            record_manual_stock_change(item=line["item"], kind=CHANGE_KIND_OPENING, qty_raw=_fmt(line["qty"]),
                                       notes=note, user=user, unit_cost_raw=_fmt(line["cost"]))
        else:
            kind = CHANGE_KIND_ADJUST_INCREASE if line["diff"] > 0 else CHANGE_KIND_ADJUST_DECREASE
            record_manual_stock_change(item=line["item"], kind=kind, qty_raw=_fmt(abs(line["diff"])),
                                       notes=note, user=user)
    return len(preview["lines"])


def template_response(mode):
    items = active_items_with_stock()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="stock_{mode}_template.csv"'
    response.write("\ufeff")
    w = csv.writer(response)
    if mode == "opening":
        w.writerow(["نام کالا", "مقدار", "بهای واحد (تومان)", "واحد"])
        for i in items:
            w.writerow([i.name, "", "", i.get_unit_display()])
    else:
        w.writerow(["نام کالا", "مقدار شمارش‌شده", "موجودی سیستم", "واحد"])
        for i in items:
            w.writerow([i.name, "", _fmt(i.stock_now), i.get_unit_display()])
    return response
