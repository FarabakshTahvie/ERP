from decimal import Decimal
import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Case, DecimalField, F, IntegerField, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from catalog.models import Item
from utils.generic_table import build_table_context
from utils.jalali import to_fa_digits, jalali_str
from utils.jalali_forms import JalaliDateField
from .services import (
    user_can_manage_inventory, create_purchase_from_form, record_manual_stock_change,
)


def _format_qty(value):
    """مقدار اعشاری را بدون صفرهای اضافه رشته می‌کند (مثلاً '2' یا '2.5')."""
    normalized = Decimal(value).normalize()
    if normalized == normalized.to_integral():
        normalized = normalized.quantize(Decimal(1))
    return format(normalized, "f")


def _stock_queryset():
    """
    جمع موجودی هر کالا از روی همه‌ی لات‌های همه‌ی انبارها (نه یک انبار ثابت) —
    همین الان هم چندانباره درست کار می‌کند، چون هیچ‌جا فرض «یک انبار» گذاشته نشده.
    Coalesce لازم است تا کالای بدون هیچ لات هم در نتیجه بماند (نه اینکه با INNER JOIN حذف شود).
    """
    return (
        Item.objects.filter(is_active=True)
        .select_related("category")
        .annotate(
            stock=Coalesce(
                Sum("lots__qty_remaining"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=4),
            )
        )
        .annotate(
            is_low=Case(
                When(reorder_point__gt=0, stock__lte=F("reorder_point"), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-is_low", "name")
    )


@login_required
@user_passes_test(user_can_manage_inventory)
def stock_table(request):
    qs = _stock_queryset()

    def row_builder(item):
        low = item.is_low == 1
        return {
            "url": None,  # در W1 ردیف‌ها کلیک‌پذیر نیستند؛ صفحه‌ی جزئیات کالا هنوز نداریم
            "cells": [
                {"type": "text", "value": item.name},
                {"type": "muted", "value": item.get_item_type_display()},
                {"type": "muted", "value": item.category.name if item.category_id else "—"},
                {"type": "muted", "value": item.get_unit_display()},
                {"type": "text", "value": to_fa_digits(_format_qty(item.stock))},
                {"type": "muted", "value": to_fa_digits(_format_qty(item.reorder_point)) if item.reorder_point else "—"},
                {"type": "badge", "value": "کمبود" if low else "عادی", "variant": "warning" if low else "success"},
            ],
        }

    context = build_table_context(
        request, qs,
        columns=[
            {"label": "کالا"}, {"label": "نوع"}, {"label": "دسته‌بندی"}, {"label": "واحد"},
            {"label": "موجودی فعلی"}, {"label": "حد هشدار"}, {"label": "وضعیت"},
        ],
        row_builder=row_builder,
        container_id="table-stock",
        param_prefix="st_",
        empty_icon="package", empty_text="هنوز کالایی در کاتالوگ فعال ثبت نشده.",
        list_url=reverse("inventory:stock_table"),
    )
    return render(request, "utils/partials/generic_table.html", context)


def _parse_json_lines(raw_value):
    try:
        data = json.loads(raw_value) if raw_value else []
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_supplier_party_data(post):
    phone = (post.get("supplier_phone_number") or "").strip()
    if not phone:
        return None
    return {
        "name": (post.get("supplier_party_name") or "").strip(),
        "brand_name": (post.get("supplier_brand_name") or "").strip(),
        "entity_type": post.get("supplier_entity_type", "individual"),
        "phone_number": phone,
        "national_code": (post.get("supplier_national_code") or "").strip() or None,
    }


@login_required
@user_passes_test(user_can_manage_inventory)
def purchase_new(request):
    if request.method == "POST":
        raw_date = (request.POST.get("purchased_at") or "").strip()
        if raw_date:
            try:
                purchase_date = JalaliDateField().clean(raw_date)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
                return redirect("inventory:purchase_new")
        else:
            purchase_date = timezone.localdate()
        purchased_at = timezone.make_aware(datetime.combine(purchase_date, timezone.localtime().time()))

        lines_raw = _parse_json_lines(request.POST.get("lines_json"))
        supplier_party_id = request.POST.get("supplier_party_id") or None
        supplier_party_data = None if supplier_party_id else _extract_supplier_party_data(request.POST)

        try:
            create_purchase_from_form(
                supplier_party_id=supplier_party_id,
                supplier_party_data=supplier_party_data,
                purchased_at=purchased_at,
                invoice_number=request.POST.get("invoice_number", ""),
                notes=request.POST.get("notes", ""),
                invoice_file=request.FILES.get("invoice_file"),
                lines_raw=lines_raw,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("inventory:purchase_new")

        messages.success(request, "خرید با موفقیت ثبت شد و موجودی کالاها به‌روزرسانی شد.")
        return redirect("home")

    return render(request, "inventory/purchase_new.html", {
        "items": Item.objects.filter(is_active=True),
        "today_jalali": jalali_str(timezone.localdate(), fmt="%Y/%m/%d"),
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def stock_movement_new(request):
    if request.method == "POST":
        item = get_object_or_404(Item, pk=request.POST.get("item_id"), is_active=True)
        try:
            record_manual_stock_change(
                item=item,
                kind=request.POST.get("kind"),
                qty_raw=request.POST.get("qty"),
                notes=request.POST.get("notes", ""),
                user=request.user,
                unit_cost_raw=request.POST.get("unit_cost"),
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("inventory:stock_movement_new")
        messages.success(request, "تغییر موجودی با موفقیت ثبت شد.")
        return redirect("home")

    return render(request, "inventory/stock_movement_new.html", {
        "items": _stock_queryset(),
    })

