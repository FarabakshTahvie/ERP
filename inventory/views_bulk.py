import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from catalog.models import Item
from .services import user_can_manage_inventory
from .bulk import (
    parse_bulk_json,
    validate_bulk_opening_lines,
    commit_bulk_opening,
    validate_bulk_reconciliation_lines,
    commit_bulk_reconciliation,
)

@login_required
@user_passes_test(user_can_manage_inventory)
def bulk_opening_page(request):
    raw_json = request.POST.get("lines_json", "[]")
    notes = (request.POST.get("notes") or "").strip()
    is_confirm = request.POST.get("confirm") == "1"

    items = Item.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        try:
            lines_data = parse_bulk_json(raw_json)
            if is_confirm:
                commit_bulk_opening(lines_data, notes, request.user)
                messages.success(request, "ثبت گروهی موجودی اولیه با موفقیت انجام شد.")
                return redirect("home")
            else:
                cleaned = validate_bulk_opening_lines(lines_data)
                if not cleaned:
                    raise ValueError("ردیفی برای پیش‌نمایش وجود ندارد.")
                return render(request, "inventory/bulk_opening_preview.html", {
                    "preview_lines": cleaned,
                    "notes": notes,
                    "lines_json": json.dumps(lines_data),
                })
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, "inventory/bulk_opening.html", {
        "items": items,
        "lines_json": raw_json,
        "notes": notes,
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def bulk_reconciliation_page(request):
    raw_json = request.POST.get("lines_json", "[]")
    notes = (request.POST.get("notes") or "").strip()
    is_confirm = request.POST.get("confirm") == "1"

    items = Item.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        try:
            lines_data = parse_bulk_json(raw_json)
            if is_confirm:
                commit_bulk_reconciliation(lines_data, notes, request.user)
                messages.success(request, "انبارگردانی اتمیک با موفقیت تایید و ثبت نهایی شد.")
                return redirect("home")
            else:
                cleaned = validate_bulk_reconciliation_lines(lines_data)
                if not cleaned:
                    raise ValueError("هیچ اختلافی بین شمارش و موجودی سیستم پیدا نشد.")
                return render(request, "inventory/bulk_reconciliation_preview.html", {
                    "preview_lines": cleaned,
                    "notes": notes,
                    "lines_json": json.dumps(lines_data),
                })
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, "inventory/bulk_reconciliation.html", {
        "items": items,
        "lines_json": raw_json,
        "notes": notes,
    })
