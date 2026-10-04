from decimal import Decimal
import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Case, DecimalField, F, IntegerField, Prefetch, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from catalog.models import Item, ItemCategory
from utils.generic_table import build_table_context, render_table
from utils.jalali import to_fa_digits, jalali_str
from utils.jalali_forms import JalaliDateField
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import StockLot
from .services import (
    user_can_manage_inventory, create_purchase_from_form, record_manual_stock_change,
    create_item, update_item, set_item_active, item_structure_locked, DuplicateItemNameError,
)


def _format_qty(value):
    """مقدار اعشاری را بدون صفرهای اضافه رشته می‌کند (مثلاً '2' یا '2.5')."""
    normalized = Decimal(value).normalize()
    if normalized == normalized.to_integral():
        normalized = normalized.quantize(Decimal(1))
    return format(normalized, "f")


def _stock_queryset(include_inactive=False):
    qs = Item.objects.all() if include_inactive else Item.objects.filter(is_active=True)
    return (
        qs.select_related("category")
        .prefetch_related(
            Prefetch("lots", queryset=StockLot.objects.filter(qty_remaining__gt=0).select_related("warehouse"),
                    to_attr="stocked_lots")
        )
        .annotate(
            stock=Coalesce(
                Sum("lots__qty_remaining"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=4),
            )
        )
        .annotate(
            is_low=Case(
                When(is_active=True, reorder_point__gt=0, stock__lte=F("reorder_point"), then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-is_active", "-is_low", "name")
    )


def _stock_table_context(request):
    qs = _stock_queryset(include_inactive=True)

    def row_builder(item):
        low = item.is_low == 1
        if not item.is_active:
            status_cell = {"type": "badge", "value": "غیرفعال", "variant": "neutral"}
        else:
            status_cell = {"type": "badge", "value": "کمبود" if low else "عادی", "variant": "warning" if low else "success"}
        warehouse_names = sorted({lot.warehouse.name for lot in item.stocked_lots})
        warehouse_display = "، ".join(warehouse_names) if warehouse_names else "—"
        return {
            "url": reverse("inventory:item_edit", args=[item.id]),
            "cells": [
                {"type": "text", "value": item.name},
                {"type": "muted", "value": item.get_item_type_display()},
                {"type": "muted", "value": item.category.name if item.category_id else "—"},
                {"type": "muted", "value": warehouse_display},
                {"type": "muted", "value": item.get_unit_display()},
                {"type": "text", "value": to_fa_digits(_format_qty(item.stock))},
                {"type": "muted", "value": to_fa_digits(_format_qty(item.reorder_point)) if item.reorder_point else "—"},
                status_cell,
            ],
        }

    category_choices = [(c.id, c.name) for c in ItemCategory.objects.order_by("name")]

    return build_table_context(
        request, qs,
        columns=[
            {"label": "کالا", "sort_field": "name", "filter_key": "active", "filter_type": "boolean",
             "filter_field": "is_active", "true_label": "فعال", "false_label": "غیرفعال"},
            {"label": "نوع", "sort_field": "item_type", "filter_key": "item_type", "filter_type": "select",
             "choices": Item.ItemType.choices},
            {"label": "دسته‌بندی", "sort_field": "category__name", "filter_key": "category", "filter_type": "select",
             "filter_field": "category_id", "choices": category_choices},
            {"label": "انبار"},
            {"label": "واحد", "sort_field": "unit"},
            {"label": "موجودی فعلی", "sort_field": "stock"},
            {"label": "حد هشدار", "sort_field": "reorder_point"},
            {"label": "وضعیت", "sort_field": "is_low", "filter_key": "low", "filter_type": "boolean",
             "filter_field": "is_low", "true_label": "کمبود", "false_label": "عادی"},
        ],
        row_builder=row_builder,
        container_id="table-stock",
        param_prefix="st_",
        empty_icon="package", empty_text="هنوز کالایی در کاتالوگ فعال ثبت نشده.",
        list_url=reverse("inventory:stock_table"),
        search_fields=["name", "category__name"],
    )


@login_required
@user_passes_test(user_can_manage_inventory)
def stock_table(request):
    return render_table(request, _stock_table_context(request))


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
        "items": Item.objects.filter(is_active=True).order_by("name"),
        "today_jalali": jalali_str(timezone.localdate(), fmt="%Y/%m/%d"),
        **item_form_choices(),
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def stock_movement_new(request):
    from projects.models import Project
    if request.method == "POST":
        try:
            from .services import get_active_item
            item = get_active_item(request.POST.get("item_id"))
            project_id = request.POST.get("project_id") or None
            related_object = None
            if project_id and project_id != "company":
                related_object = get_object_or_404(Project, id=project_id)
            elif request.POST.get("kind") == "consume" and project_id == "company":
                # مصرف داخلی شرکت
                # یک نمونه ساختگی یا هندلینگ بر اساس نیاز برای جلوگیری از خطای الزامی بودن
                from core.models import Party
                related_object = Party.objects.filter(is_partner=True).first() # به عنوان مثال
            
            record_manual_stock_change(
                item=item,
                kind=request.POST.get("kind"),
                qty_raw=request.POST.get("qty"),
                notes=request.POST.get("notes", ""),
                user=request.user,
                unit_cost_raw=request.POST.get("unit_cost"),
                related_object=related_object,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("inventory:stock_movement_new")
        messages.success(request, "تغییر موجودی با موفقیت ثبت شد.")
        return redirect("home")

    projects = Project.objects.filter(status=Project.Status.IN_PROGRESS).order_by("name")
    return render(request, "inventory/stock_movement_new.html", {
        "items": _stock_queryset(),
        "projects": projects,
    })


def _stock_tab_url():
    return reverse("home") + "?tab=stock"


def item_form_choices():
    return {
        "type_choices": Item.ItemType.choices,
        "unit_choices": Item.Unit.choices,
        "categories": ItemCategory.objects.order_by("name"),
    }


def _parse_specs_json(raw):
    """None = ارسال نشده. JSON خراب خطا می‌دهد (نه لیست خالی که مشخصات را پاک می‌کرد)."""
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("مشخصات فنی نامعتبر است؛ صفحه را دوباره باز کنید.")
    if not isinstance(data, list):
        raise ValueError("مشخصات فنی نامعتبر است؛ صفحه را دوباره باز کنید.")
    return data


def _item_specs_list(item):
    specs = item.specs if isinstance(item.specs, dict) else {}
    return [{"key": str(k), "value": str(v)} for k, v in specs.items()]


def _item_values_from_post(post):
    return {
        "name": post.get("name", ""), "item_type": post.get("item_type", ""), "unit": post.get("unit", ""),
        "category_id": post.get("category_id", ""), "new_category_name": post.get("new_category_name", ""),
        "reorder_point": post.get("reorder_point", ""),
    }


def _item_values_from_item(item):
    return {
        "name": item.name, "item_type": item.item_type, "unit": item.unit,
        "category_id": item.category_id or "", "new_category_name": "",
        "reorder_point": _format_qty(item.reorder_point),
    }


def _render_item_form(request, *, item, values, specs, locked, duplicate_warning):
    return render(request, "inventory/item_form.html", {
        **item_form_choices(),
        "item": item, "values": values, "specs": specs, "locked": locked,
        "duplicate_warning": duplicate_warning,
        "current_stock_display": to_fa_digits(_format_qty(item.current_stock)) if item else "",
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def item_new(request):
    values, specs, duplicate_warning = {}, [], None
    if request.method == "POST":
        values = _item_values_from_post(request.POST)
        try:
            specs_pairs = _parse_specs_json(request.POST.get("specs_json"))
            specs = specs_pairs or []
            item = create_item(
                name=values["name"], item_type=values["item_type"], unit=values["unit"],
                category_id=values["category_id"], new_category_name=values["new_category_name"],
                reorder_point_raw=values["reorder_point"], specs_pairs=specs_pairs,
                confirm_duplicate=request.POST.get("confirm_duplicate") == "1",
            )
        except DuplicateItemNameError as e:
            duplicate_warning = str(e)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"کالای «{item.name}» ثبت شد.")
            return redirect(_stock_tab_url())
    return _render_item_form(request, item=None, values=values, specs=specs, locked=False,
                             duplicate_warning=duplicate_warning)


@login_required
@user_passes_test(user_can_manage_inventory)
def item_edit(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    locked = item_structure_locked(item)
    duplicate_warning = None
    if request.method == "POST":
        values = _item_values_from_post(request.POST)
        specs_pairs = None
        try:
            specs_pairs = _parse_specs_json(request.POST.get("specs_json"))
            update_item(
                item, name=values["name"], item_type=values["item_type"], unit=values["unit"],
                category_id=values["category_id"], new_category_name=values["new_category_name"],
                reorder_point_raw=values["reorder_point"], specs_pairs=specs_pairs,
                confirm_duplicate=request.POST.get("confirm_duplicate") == "1",
            )
        except DuplicateItemNameError as e:
            duplicate_warning = str(e)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"تغییرات کالای «{values['name'].strip()}» ذخیره شد.")
            return redirect(_stock_tab_url())
        if locked:   # کنترل‌های disabled ارسال نمی‌شوند؛ برای نمایش، مقدار فعلی
            values["item_type"], values["unit"] = item.item_type, item.unit
        specs = specs_pairs if specs_pairs is not None else _item_specs_list(item)
    else:
        values, specs = _item_values_from_item(item), _item_specs_list(item)
    return _render_item_form(request, item=item, values=values, specs=specs, locked=locked,
                             duplicate_warning=duplicate_warning)


@login_required
@user_passes_test(user_can_manage_inventory)
@require_POST
def item_toggle_active(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    target = not item.is_active
    try:
        set_item_active(item, active=target)
        messages.success(request, f"کالای «{item.name}» {'فعال' if target else 'غیرفعال'} شد.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("inventory:item_edit", item.id)


@login_required
@user_passes_test(user_can_manage_inventory)
@require_POST
def item_quick_create(request):
    """ساخت سریع کالا از داخل فرم خرید (JSON)."""
    try:
        item = create_item(
            name=request.POST.get("name"), item_type=request.POST.get("item_type"),
            unit=request.POST.get("unit"), category_id=request.POST.get("category_id"),
            reorder_point_raw=request.POST.get("reorder_point", ""),
            confirm_duplicate=request.POST.get("confirm_duplicate") == "1",
        )
    except DuplicateItemNameError as e:
        return JsonResponse({"ok": False, "duplicate": True, "error": str(e)}, status=409)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "item": {"id": item.id, "name": item.name, "unit": item.get_unit_display()}})

