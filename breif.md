## بریف: مدیریت انبارها + انتخاب انبار + انتقال + حذف امن کالا

**قواعد ثابت پروژه را رعایت کن** (آیکون فقط از sprite.svg، `data-money`/`data-decimal` به‌جای `type="number"`، کلاس‌های Tailwind v4/daisyUI v5 موجود، شاخه‌ی تازه از main، بدون merge بدون اجازه). هیچ تستی ننویس. هیچ مایگریشنی لازم نیست (مدل‌ها دست نمی‌خورند).

### گام ۱ — `inventory/services.py`

به بالای فایل چیزی اضافه نمی‌خواهد (`Warehouse`, `Purchase`, `PurchaseLine` از قبل ایمپورت‌اند).

**۱.۱) تابع تشخیص دسترسی به مدیریت انبار** (بعد از `user_can_manage_inventory`):
```python
def user_can_manage_warehouses(user):
    """برخلاف user_can_manage_inventory، مدیر را هم شامل می‌شود؛ چون مدیریت انبارها کار ساختاری است."""
    from core.capabilities import is_manager
    return user_can_manage_inventory(user) or is_manager(user)
```

**۱.۲) CRUD انبار** (همان‌جا کنار تابع بالا):
```python
WAREHOUSE_NAME_MAX = 100


@transaction.atomic
def create_warehouse(*, name, is_default=False):
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("نام انبار را بنویسید.")
    if len(name) > WAREHOUSE_NAME_MAX:
        raise ValueError(f"نام انبار نباید بیش از {WAREHOUSE_NAME_MAX} نویسه باشد.")
    if Warehouse.objects.filter(name__iexact=name).exists():
        raise ValueError("انباری با همین نام از قبل وجود دارد.")
    warehouse = Warehouse.objects.create(name=name, is_default=False)
    if is_default or not Warehouse.objects.exclude(pk=warehouse.pk).filter(is_default=True).exists():
        set_default_warehouse(warehouse)
    return warehouse


@transaction.atomic
def update_warehouse(*, warehouse, name):
    name = " ".join((name or "").split())
    if not name:
        raise ValueError("نام انبار را بنویسید.")
    if len(name) > WAREHOUSE_NAME_MAX:
        raise ValueError(f"نام انبار نباید بیش از {WAREHOUSE_NAME_MAX} نویسه باشد.")
    if Warehouse.objects.exclude(pk=warehouse.pk).filter(name__iexact=name).exists():
        raise ValueError("انباری با همین نام از قبل وجود دارد.")
    warehouse.name = name
    warehouse.save(update_fields=["name"])
    return warehouse


@transaction.atomic
def set_default_warehouse(warehouse):
    Warehouse.objects.exclude(pk=warehouse.pk).update(is_default=False)
    Warehouse.objects.filter(pk=warehouse.pk).update(is_default=True)
```
(عمداً تابع حذف انبار نساختیم؛ چون `Warehouse` فیلد فعال/غیرفعال ندارد و حذفش با PROTECT در StockLot/PurchaseLine/SaleLine همیشه خطا می‌دهد. فقط ثبت، ویرایش، پیش‌فرض‌کردن.)

**۱.۳) انتقال بین انبارها** (بعد از تابع `consume_stock`):
```python
@transaction.atomic
def transfer_stock(*, item, qty_raw, from_warehouse, to_warehouse, user, notes):
    """خروج FIFO از انبار مبدا و ورود به انبار مقصد با همان بهای میانگین موزون همان خروج."""
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("دلیل انتقال را بنویسید.")
    if from_warehouse.pk == to_warehouse.pk:
        raise ValueError("انبار مبدا و مقصد نباید یکی باشند.")
    assert_stockable(item)
    qty = parse_decimal_input(qty_raw, label="مقدار")
    breakdown = consume_stock(
        item=item, qty=qty, user=user, warehouse=from_warehouse,
        movement_type=StockMovement.MovementType.TRANSFER,
        notes=f"انتقال به «{to_warehouse.name}» — {notes}"[:255],
    )
    moved_qty = sum((take for _lot, take, _cost in breakdown), Decimal("0"))
    moved_value = sum((take * cost for _lot, take, cost in breakdown), Decimal("0"))
    avg_cost = (moved_value / moved_qty) if moved_qty else Decimal("0")
    receive_stock(
        item=item, warehouse=to_warehouse, qty=moved_qty, unit_cost=avg_cost, received_at=timezone.now(),
        movement_type=StockMovement.MovementType.TRANSFER, direction=StockMovement.Direction.IN,
        notes=f"انتقال از «{from_warehouse.name}» — {notes}"[:255], created_by=user,
    )
    return moved_qty
```

**۱.۴) `record_manual_stock_change` را طوری عوض کن که انبار بگیرد.**
پیدا کن:
```python
def record_manual_stock_change(*, item, kind, qty_raw, notes, user, unit_cost_raw=None, related_object=None,
                               movement_date=None, internal=False):
```
جایگزین کن با:
```python
def record_manual_stock_change(*, item, kind, qty_raw, notes, user, unit_cost_raw=None, related_object=None,
                               movement_date=None, internal=False, warehouse=None):
```
داخل همان تابع، این دو خط:
```python
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.OUT,
                      related_object=related_object, movement_date=target_date)
        return
    if kind == CHANGE_KIND_ADJUST_DECREASE:
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.ADJUST,
                      related_object=related_object, movement_date=target_date)
```
را به
```python
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.OUT,
                      related_object=related_object, movement_date=target_date, warehouse=warehouse)
        return
    if kind == CHANGE_KIND_ADJUST_DECREASE:
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.ADJUST,
                      related_object=related_object, movement_date=target_date, warehouse=warehouse)
```
و این خط:
```python
    warehouse = Warehouse.objects.filter(is_default=True).first()
    if not warehouse:
        raise ValueError("هیچ انبار پیش‌فرضی تعریف نشده است؛ ابتدا از پنل ادمین یک انبار با «انبار پیش‌فرض» فعال بسازید.")
```
را (همان بخش بعد از شاخه‌ی consume/adjust_decrease) به:
```python
    warehouse = warehouse or Warehouse.objects.filter(is_default=True).first()
    if not warehouse:
        raise ValueError("هیچ انباری تعریف نشده؛ ابتدا از «انبارها» یک انبار بساز.")
```

**۱.۵) خرید: هر ردیف انبار خودش را داشته باشد.**
`_clean_purchase_lines` را جایگزین کن:
```python
def _clean_purchase_lines(raw_lines):
    cleaned = []
    for raw in (raw_lines or []):
        try:
            item_id = int(raw["id"])
            warehouse_id = int(raw["warehouse_id"])
            qty = Decimal(str(raw["qty"]))
            unit_cost = Decimal(str(raw["unit_cost"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValueError("اطلاعات ردیف‌های خرید نامعتبر است؛ انبار هر ردیف را هم انتخاب کن.")
        if not qty.is_finite() or not unit_cost.is_finite() or qty <= 0 or unit_cost <= 0:
            raise ValueError("در ردیف‌های خرید، مقدار و بهای واحد باید بزرگ‌تر از صفر باشند.")
        cleaned.append({"item_id": item_id, "warehouse_id": warehouse_id, "qty": qty, "unit_cost": unit_cost})
    ids = {c["item_id"] for c in cleaned}
    if ids and Item.objects.filter(pk__in=ids, is_active=True).count() != len(ids):
        raise ValueError("یکی از کالاهای انتخاب‌شده در سیستم پیدا نشد یا غیرفعال است.")
    blocked = list(Item.objects.filter(pk__in=ids, item_type=Item.ItemType.MANUFACTURED)
                   .values_list("name", flat=True))
    if blocked:
        raise ValueError("این کالاها ساختنی‌اند و خرید نمی‌شوند: " + "، ".join(blocked))
    wh_ids = {c["warehouse_id"] for c in cleaned}
    if wh_ids and Warehouse.objects.filter(pk__in=wh_ids).count() != len(wh_ids):
        raise ValueError("انبار یکی از ردیف‌ها معتبر نیست.")
    return cleaned
```
و `create_purchase_from_form` را جایگزین کن:
```python
@transaction.atomic
def create_purchase_from_form(*, supplier_party_id=None, supplier_party_data=None,
                              purchased_at, invoice_number="", notes="", lines_raw):
    from core.periods import assert_open
    assert_open(purchased_at, "خرید")
    lines = _clean_purchase_lines(lines_raw)
    if not lines:
        raise ValueError("حداقل یک ردیف کالا باید وارد شود.")

    supplier = _resolve_supplier_party(party_id=supplier_party_id, party_data=supplier_party_data)
    purchase = Purchase.objects.create(
        supplier=supplier, invoice_number=(invoice_number or "").strip(),
        notes=(notes or "").strip(), purchased_at=purchased_at,
    )
    items_by_id = {i.pk: i for i in Item.objects.filter(pk__in=[l["item_id"] for l in lines])}
    warehouses_by_id = {w.pk: w for w in Warehouse.objects.filter(pk__in=[l["warehouse_id"] for l in lines])}
    for line in lines:
        item = items_by_id[line["item_id"]]
        warehouse = warehouses_by_id[line["warehouse_id"]]
        purchase_line = PurchaseLine.objects.create(
            purchase=purchase, item=item, warehouse=warehouse,
            qty=line["qty"], unit_cost=line["unit_cost"],
        )
        receive_stock(
            item=item, warehouse=warehouse, qty=line["qty"], unit_cost=line["unit_cost"],
            received_at=purchased_at, purchase_line=purchase_line,
        )
    return purchase
```

**۱.۶) حذف واقعی کالای بی‌مصرف** (بعد از `item_structure_locked`):
```python
def item_truly_unused(item):
    """کامل‌تر از item_structure_locked: فروش و حرکت انبار را هم می‌بیند. فقط برای حذف واقعی استفاده شود."""
    return not (item_structure_locked(item) or item.sale_lines.exists() or item.movements.exists())


@transaction.atomic
def delete_unused_item(*, item, actor):
    if not user_can_manage_inventory(actor):
        raise ValueError("شما اجازه‌ی حذف کالا را ندارید.")
    if not item_truly_unused(item):
        raise ValueError("این کالا قبلاً در خرید، انبار، پروژه یا فروش استفاده شده؛ حذف نمی‌شود. به‌جایش غیرفعالش کن.")
    name = item.name
    item.delete()
    return name
```

---

### گام ۲ — `finance/accounting.py`

`add_purchase_line` را جایگزین کن (یک پارامتر `warehouse_id` اضافه شد):
```python
@transaction.atomic
def add_purchase_line(*, purchase, actor, item_id, warehouse_id, qty_raw, unit_cost_raw):
    from core.capabilities import can
    from core.periods import assert_open
    from inventory.models import Purchase, PurchaseLine, Warehouse
    from inventory.services import get_active_item, parse_decimal_input, receive_stock
    if not can(actor, "purchases.edit"):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند ردیف خرید اضافه کند.")
    purchase = Purchase.objects.select_for_update(of=("self",)).select_related("supplier").get(pk=purchase.pk)
    assert_open(purchase.purchased_at, "اصلاح خرید")
    item = get_active_item(item_id)
    try:
        warehouse = Warehouse.objects.get(pk=int(warehouse_id))
    except (TypeError, ValueError, Warehouse.DoesNotExist):
        raise ValueError("انبار را از فهرست انتخاب کن.")
    qty = parse_decimal_input(qty_raw, label="مقدار")
    cost = parse_decimal_input(unit_cost_raw, label="بهای واحد")
    if qty > Decimal("9999999") or cost > Decimal("1000000000000"):
        raise ValueError("مقدار یا بهای واحد بیش از حد بزرگ است.")
    qty, cost = qty.quantize(QTY_Q), cost.quantize(Decimal("0.01"))
    if qty <= 0 or cost <= 0:
        raise ValueError("مقدار و بهای واحد باید بزرگ‌تر از صفر باشند.")
    line = PurchaseLine.objects.create(purchase=purchase, item=item, warehouse=warehouse, qty=qty, unit_cost=cost)
    receive_stock(item=item, warehouse=warehouse, qty=qty, unit_cost=cost,
                  received_at=purchase.purchased_at, purchase_line=line)
    log_event(kind=AccountingEvent.Kind.PURCHASE, purchase=purchase, actor=actor,
              amount=(qty * cost).quantize(Decimal("1")),
              text=f"افزودن ردیف به خرید از «{purchase.supplier.name}»: {item.name} (انبار {warehouse.name})")
    return line
```

### گام ۳ — `finance/views_accounting.py`

در `purchase_line_add` پیدا کن:
```python
        line = accounting.add_purchase_line(
            purchase=purchase, actor=request.user, item_id=request.POST.get("item_id"),
            qty_raw=request.POST.get("qty"), unit_cost_raw=request.POST.get("unit_cost"))
```
جایگزین کن:
```python
        line = accounting.add_purchase_line(
            purchase=purchase, actor=request.user, item_id=request.POST.get("item_id"),
            warehouse_id=request.POST.get("warehouse_id"),
            qty_raw=request.POST.get("qty"), unit_cost_raw=request.POST.get("unit_cost"))
```
در `purchase_detail` پیدا کن:
```python
    if can(request.user, "purchases.edit"):
        from inventory.services import stockable_items
        from inventory.views import item_form_choices
        ctx["line_items"] = [{"id": i.id, "name": i.name, "unit": i.get_unit_display()}
                             for i in stockable_items().order_by("name")]
        ctx.update(item_form_choices())
```
جایگزین کن:
```python
    if can(request.user, "purchases.edit"):
        from inventory.services import stockable_items
        from inventory.views import item_form_choices
        ctx["line_items"] = [{"id": i.id, "name": i.name, "unit": i.get_unit_display()}
                             for i in stockable_items().order_by("name")]
        ctx["warehouses"] = Warehouse.objects.order_by("-is_default", "name")
        ctx.update(item_form_choices())
```

### گام ۴ — `inventory/views.py`

بالای فایل، پیدا کن:
```python
from .models import StockLot
```
جایگزین کن:
```python
from .models import StockLot, Warehouse
```
پیدا کن:
```python
from .services import (
    user_can_manage_inventory, user_can_create_purchases, user_can_create_items, create_purchase_from_form, record_manual_stock_change,
    create_item, update_item, set_item_active, item_structure_locked, DuplicateItemNameError, add_purchase_file, stockable_items
)
```
جایگزین کن:
```python
from .services import (
    user_can_manage_inventory, user_can_create_purchases, user_can_create_items, create_purchase_from_form, record_manual_stock_change,
    create_item, update_item, set_item_active, item_structure_locked, DuplicateItemNameError, add_purchase_file, stockable_items,
    user_can_manage_warehouses, create_warehouse, update_warehouse, set_default_warehouse, transfer_stock,
    delete_unused_item, item_truly_unused, get_active_item,
)
```

`purchase_new` ویو: پیدا کن
```python
    return render(request, "inventory/purchase_new.html", {
        "items": stockable_items().order_by("name"),
        "today_jalali": jalali_str(timezone.localdate(), fmt="%Y/%m/%d"),
        **item_form_choices(),
    })
```
جایگزین کن:
```python
    return render(request, "inventory/purchase_new.html", {
        "items": stockable_items().order_by("name"),
        "today_jalali": jalali_str(timezone.localdate(), fmt="%Y/%m/%d"),
        "warehouses": Warehouse.objects.order_by("-is_default", "name"),
        **item_form_choices(),
    })
```

`_movement_page` را جایگزین کن:
```python
def _movement_page(request):
    from projects.models import Project
    return render(request, "inventory/stock_movement_new.html", {
        "items": _stock_queryset().exclude(item_type=Item.ItemType.MANUFACTURED),
        "projects": Project.objects.filter(status=Project.Status.IN_PROGRESS).order_by("name"),
        "warehouses": Warehouse.objects.order_by("-is_default", "name"),
    })
```

`stock_movement_new` ویو: پیدا کن
```python
            record_manual_stock_change(
                item=item, kind=kind, qty_raw=request.POST.get("qty"),
                notes=request.POST.get("notes", ""), user=request.user,
                unit_cost_raw=request.POST.get("unit_cost"),
                related_object=related_object, internal=internal,
            )
```
جایگزین کن:
```python
            warehouse = None
            raw_wh = request.POST.get("warehouse_id")
            if raw_wh:
                warehouse = get_object_or_404(Warehouse, pk=raw_wh)
            record_manual_stock_change(
                item=item, kind=kind, qty_raw=request.POST.get("qty"),
                notes=request.POST.get("notes", ""), user=request.user,
                unit_cost_raw=request.POST.get("unit_cost"),
                related_object=related_object, internal=internal, warehouse=warehouse,
            )
```

در انتهای فایل (بعد از `item_quick_create`) این‌ها را اضافه کن:
```python
@login_required
@user_passes_test(user_can_manage_warehouses)
def warehouse_list(request):
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create":
                create_warehouse(name=request.POST.get("name", ""), is_default=request.POST.get("is_default") == "on")
            elif action == "edit":
                wh = get_object_or_404(Warehouse, pk=request.POST.get("warehouse_id"))
                update_warehouse(warehouse=wh, name=request.POST.get("name", ""))
            elif action == "set_default":
                wh = get_object_or_404(Warehouse, pk=request.POST.get("warehouse_id"))
                set_default_warehouse(wh)
            else:
                raise ValueError("عملیات نامعتبر است.")
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "ذخیره شد.")
        return redirect("inventory:warehouse_list")
    return render(request, "inventory/warehouse_list.html", {
        "warehouses": Warehouse.objects.order_by("-is_default", "name"),
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def stock_transfer_new(request):
    if request.method == "POST":
        try:
            from_wh = get_object_or_404(Warehouse, pk=request.POST.get("from_warehouse_id"))
            to_wh = get_object_or_404(Warehouse, pk=request.POST.get("to_warehouse_id"))
            item = get_active_item(request.POST.get("item_id"))
            transfer_stock(item=item, qty_raw=request.POST.get("qty"), from_warehouse=from_wh, to_warehouse=to_wh,
                           user=request.user, notes=request.POST.get("notes", ""))
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("inventory:stock_transfer_new")
        messages.success(request, "انتقال بین انبارها ثبت شد.")
        return redirect("home")
    return render(request, "inventory/stock_transfer_new.html", {
        "items": _stock_queryset().exclude(item_type=Item.ItemType.MANUFACTURED),
        "warehouses": Warehouse.objects.order_by("name"),
    })


@login_required
@user_passes_test(user_can_manage_inventory)
@require_POST
def item_delete(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    try:
        name = delete_unused_item(item=item, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("inventory:item_edit", item.id)
    messages.success(request, f"کالای «{name}» برای همیشه حذف شد.")
    return redirect(_stock_tab_url())
```

تابع `item_edit` را پیدا کن و خط `locked = item_structure_locked(item)` را همین‌جوری نگه دار، فقط زیرش اضافه کن `can_delete = item_truly_unused(item)` و در هر دو فراخوانی `_render_item_form` داخل همین تابع، آرگومان `can_delete=can_delete` را اضافه کن. تابع `_render_item_form` را هم عوض کن:
```python
def _render_item_form(request, *, item, values, specs, locked, duplicate_warning, can_delete=False):
    return render(request, "inventory/item_form.html", {
        **item_form_choices(),
        "item": item, "values": values, "specs": specs, "locked": locked,
        "duplicate_warning": duplicate_warning, "can_delete": can_delete,
        "current_stock_display": to_fa_digits(_format_qty(item.current_stock)) if item else "",
    })
```

### گام ۵ — `inventory/urls.py`

اضافه کن:
```python
    path("inventory/warehouses/", views.warehouse_list, name="warehouse_list"),
    path("inventory/stock-transfer/", views.stock_transfer_new, name="stock_transfer_new"),
    path("inventory/items/<int:item_id>/delete/", views.item_delete, name="item_delete"),
```

### گام ۶ — `utils/navigation.py` (اجباری — وگرنه نگهبان مسیرها می‌شکند)

به `PAGE_PARENTS` اضافه کن:
```python
    "inventory:warehouse_list": ("home", [], {"tab": "stock"}),
    "inventory:stock_transfer_new": ("home", [], {}),
```
به مجموعه‌ی `NON_PAGE` اضافه کن:
```python
    "inventory:item_delete",
```

### گام ۷ — قالب‌های تازه

**`templates/inventory/warehouse_list.html`** (تازه):
```html
{% extends "base.html" %}
{% load custom_tags %}
{% block title %}انبارها | فرابخش{% endblock %}
{% block content %}
<div class="fb-page fb-page--sm">
    <div>
        <a href="{% url 'home' %}?tab=stock" class="link link-hover text-sm fb-muted">بازگشت به موجودی انبار</a>
        <h1 class="fb-page-title mt-2">انبارها</h1>
        <p class="fb-page-sub">انبار پیش‌فرض همان‌جایی است که اگر هنگام ثبت مصرف/تعدیل انباری انتخاب نشود، استفاده می‌شود.</p>
    </div>

    <section class="fb-card fb-pad flex flex-col gap-3">
        <h2 class="fb-section-title">انبار جدید</h2>
        <form method="post" data-fb-once class="flex flex-col gap-3">
            {% csrf_token %}
            <input type="hidden" name="action" value="create">
            <div class="fb-field">
                <label class="fb-label" for="wh-new-name">نام انبار</label>
                <input type="text" id="wh-new-name" name="name" required maxlength="100" class="input w-full">
            </div>
            <label class="flex items-center gap-2 cursor-pointer text-sm">
                <input type="checkbox" name="is_default" class="checkbox checkbox-sm"> انبار پیش‌فرض باشد
            </label>
            <button type="submit" class="btn btn-primary btn-sm self-start">ثبت انبار</button>
        </form>
    </section>

    <section class="fb-card fb-pad flex flex-col gap-3">
        <h2 class="fb-section-title">انبارهای موجود</h2>
        {% for w in warehouses %}
        <div class="fb-inset flex items-center justify-between gap-3 flex-wrap">
            <form method="post" data-fb-once class="flex items-center gap-2 flex-1 min-w-48">
                {% csrf_token %}
                <input type="hidden" name="action" value="edit">
                <input type="hidden" name="warehouse_id" value="{{ w.id }}">
                <input type="text" name="name" value="{{ w.name }}" required maxlength="100" class="input input-sm flex-1 min-w-0">
                <button type="submit" class="btn btn-soft btn-sm">ذخیره</button>
            </form>
            {% if w.is_default %}
            <span class="fb-badge fb-badge-success">پیش‌فرض</span>
            {% else %}
            <form method="post" data-fb-once>
                {% csrf_token %}
                <input type="hidden" name="action" value="set_default">
                <input type="hidden" name="warehouse_id" value="{{ w.id }}">
                <button type="submit" class="btn btn-ghost btn-sm">پیش‌فرض کن</button>
            </form>
            {% endif %}
        </div>
        {% empty %}
        <p class="fb-hint">هنوز انباری ثبت نشده.</p>
        {% endfor %}
    </section>
</div>
{% endblock %}
```

**`templates/inventory/stock_transfer_new.html`** (تازه):
```html
{% extends "base.html" %}
{% load static custom_tags %}
{% block title %}انتقال بین انبارها | فرابخش{% endblock %}
{% block content %}
<div class="fb-page fb-page--sm">
    <div>
        <h1 class="fb-page-title">انتقال موجودی بین انبارها</h1>
        <p class="fb-page-sub">مقدار از انبار مبدا کم و به انبار مقصد با همان بهای میانگین اضافه می‌شود.</p>
    </div>

    <form method="post" data-fb-once class="fb-card fb-pad flex flex-col gap-4" id="transfer-form">
        {% csrf_token %}
        <div class="grid grid-cols-2 gap-3">
            <div class="fb-field">
                <label class="fb-label" for="from-wh">از انبار</label>
                <select id="from-wh" name="from_warehouse_id" required class="select w-full">
                    <option value="">انتخاب کن...</option>
                    {% for w in warehouses %}<option value="{{ w.id }}">{{ w.name }}</option>{% endfor %}
                </select>
            </div>
            <div class="fb-field">
                <label class="fb-label" for="to-wh">به انبار</label>
                <select id="to-wh" name="to_warehouse_id" required class="select w-full">
                    <option value="">انتخاب کن...</option>
                    {% for w in warehouses %}<option value="{{ w.id }}">{{ w.name }}</option>{% endfor %}
                </select>
            </div>
        </div>

        <div class="fb-field">
            <span class="fb-label">کالا</span>
            <div id="transfer-item-picker"></div>
            <input type="hidden" name="item_id" id="transfer-item-id">
            <span id="transfer-item-error" class="fb-error hidden">یک کالا از فهرست انتخاب کن.</span>
        </div>

        <div class="fb-field">
            <label class="fb-label" for="transfer-qty">مقدار</label>
            <input type="text" id="transfer-qty" name="qty" required data-decimal dir="ltr" inputmode="decimal" autocomplete="off" class="input w-full font-technical">
        </div>

        <div class="fb-field">
            <label class="fb-label" for="transfer-notes">دلیل (اجباری)</label>
            <textarea id="transfer-notes" name="notes" required rows="2" class="textarea w-full"></textarea>
        </div>

        <button type="submit" class="btn btn-primary w-full">ثبت انتقال</button>
    </form>
</div>

<script id="transfer-items-data" type="application/json">
    [{% for it in items %}{"id": {{ it.id }}, "name": "{{ it.name|escapejs }}", "unit": "{{ it.get_unit_display|escapejs }}"}{% if not forloop.last %},{% endif %}{% endfor %}]
</script>
{% endblock %}

{% block extra_js %}
<script src="{% static_v 'js/item_picker.js' %}"></script>
<script>
(function () {
    var data = JSON.parse(document.getElementById('transfer-items-data').textContent);
    var picker = fbItemPicker({ items: data, ariaLabel: 'جستجوی کالا', onSelect: function (it) {
        document.getElementById('transfer-item-id').value = it ? it.id : '';
        if (it) document.getElementById('transfer-item-error').classList.add('hidden');
    }});
    document.getElementById('transfer-item-picker').appendChild(picker.el);

    document.getElementById('transfer-form').addEventListener('submit', function (e) {
        var from = document.getElementById('from-wh').value, to = document.getElementById('to-wh').value;
        if (from && to && from === to) {
            e.preventDefault();
            window.alert('انبار مبدا و مقصد نباید یکی باشند.');
            return;
        }
        if (!document.getElementById('transfer-item-id').value) {
            e.preventDefault();
            document.getElementById('transfer-item-error').classList.remove('hidden');
            picker.focus();
        }
    });
})();
</script>
{% endblock %}
```

### گام ۸ — افزودن انتخاب انبار به قالب‌های موجود

**`templates/inventory/partials/purchase_lines_editor.html`**: داخل `<template id="purchase-row-template">`، درست بعد از `<div data-picker></div>` و قبل از کادر مقدار، این را اضافه کن:
```html
<select data-warehouse aria-label="انبار" class="select select-sm w-32">
    {% for w in warehouses %}<option value="{{ w.id }}" {% if w.is_default %}selected{% endif %}>{{ w.name }}</option>{% endfor %}
</select>
```
و پیام هشدار ردیف را به `کالا، انبار، مقدار و بهای واحد را وارد کنید...` به‌روز کن.

در `<script>` همان فایل، داخل تابع `sync()`، پیدا کن:
```js
            var id = row._picker ? row._picker.getId() : null;
            var qty = row.querySelector('[data-qty]').value.trim();
            var cost = digits(row.querySelector('[data-cost]').value);
            var qtyNum = parseFloat(qty) || 0;
            var costNum = parseFloat(cost) || 0;
            var line = qtyNum * costNum;
            row.querySelector('[data-line-total]').textContent = fmt(line);
            row.querySelector('[data-row-warn]').classList.toggle('hidden', !!id && qtyNum > 0 && costNum > 0);
            if (id && qtyNum > 0 && costNum > 0) {
                out.push({ id: id, qty: qty, unit_cost: cost });
                grand += line;
            }
```
جایگزین کن:
```js
            var id = row._picker ? row._picker.getId() : null;
            var warehouseId = row.querySelector('[data-warehouse]').value;
            var qty = row.querySelector('[data-qty]').value.trim();
            var cost = digits(row.querySelector('[data-cost]').value);
            var qtyNum = parseFloat(qty) || 0;
            var costNum = parseFloat(cost) || 0;
            var line = qtyNum * costNum;
            row.querySelector('[data-line-total]').textContent = fmt(line);
            row.querySelector('[data-row-warn]').classList.toggle('hidden', !!id && !!warehouseId && qtyNum > 0 && costNum > 0);
            if (id && warehouseId && qtyNum > 0 && costNum > 0) {
                out.push({ id: id, warehouse_id: warehouseId, qty: qty, unit_cost: cost });
                grand += line;
            }
```

**`templates/inventory/stock_movement_new.html`**: بعد از کادر انتخاب کالا (بخش `<div class="fb-field" id="project-field">`)، یک فیلد اضافه کن:
```html
<div class="fb-field">
    <label class="fb-label" for="movement-warehouse">انبار</label>
    <select id="movement-warehouse" name="warehouse_id" class="select w-full">
        <option value="">پیش‌فرض (برای افزایش) / همه‌ی انبارها (برای مصرف و کسری)</option>
        {% for w in warehouses %}<option value="{{ w.id }}">{{ w.name }}</option>{% endfor %}
    </select>
</div>
```
در `<script>` همان فایل، داخل `syncKind()`، همان‌جایی که `needsCost` ساخته می‌شود این خط را اضافه کن:
```js
el('movement-warehouse').required = needsCost;
```

**`templates/finance/accounting_purchase.html`**: داخل `#purchase-line-panel`، درست بعد از بلوک `<div data-line-picker></div><input type="hidden" name="item_id"></div>` و قبل از `<div class="grid grid-cols-2 gap-2">` این را اضافه کن:
```html
<div class="fb-field">
    <label class="fb-label" for="line-warehouse">انبار</label>
    <select id="line-warehouse" name="warehouse_id" required class="select select-sm w-full">
        {% for w in warehouses %}<option value="{{ w.id }}" {% if w.is_default %}selected{% endif %}>{{ w.name }}</option>{% endfor %}
    </select>
</div>
```

**`static/js/purchase_lines.js`**: پیدا کن
```js
  var hidden = form.querySelector('input[name=item_id]');
  var qty = form.querySelector('input[name=qty]'), cost = form.querySelector('input[name=unit_cost]');
```
جایگزین کن:
```js
  var hidden = form.querySelector('input[name=item_id]');
  var warehouseSelect = form.querySelector('select[name=warehouse_id]');
  var qty = form.querySelector('input[name=qty]'), cost = form.querySelector('input[name=unit_cost]');
```
و در شنونده‌ی submit پیدا کن:
```js
    if (!hidden.value) { say(err, 'کالا را از فهرست انتخاب کنید.'); return; }
    if (!q) { say(err, 'مقدار را بنویسید.'); return; }
    if (!c) { say(err, 'بهای واحد را بنویسید.'); return; }
    say(null, '');
    btn.disabled = true;
    var fd = new FormData();
    fd.append('item_id', hidden.value);
    fd.append('qty', q);
    fd.append('unit_cost', c);
```
جایگزین کن:
```js
    if (!hidden.value) { say(err, 'کالا را از فهرست انتخاب کنید.'); return; }
    if (!warehouseSelect.value) { say(err, 'انبار را انتخاب کنید.'); return; }
    if (!q) { say(err, 'مقدار را بنویسید.'); return; }
    if (!c) { say(err, 'بهای واحد را بنویسید.'); return; }
    say(null, '');
    btn.disabled = true;
    var fd = new FormData();
    fd.append('item_id', hidden.value);
    fd.append('warehouse_id', warehouseSelect.value);
    fd.append('qty', q);
    fd.append('unit_cost', c);
```

**`templates/inventory/item_form.html`**: بعد از بلوک فرم toggle-active موجود (`{% if item %}...{% endif %}` انتهای فایل)، این را اضافه کن:
```html
{% if item and can_delete %}
<form method="post" action="{% url 'inventory:item_delete' item.id %}" data-fb-once
      onsubmit="return confirm('این کالا برای همیشه حذف شود؟ برگشت ندارد.');"
      class="fb-card fb-pad flex items-center justify-between gap-3">
    {% csrf_token %}
    <span class="text-xs fb-muted">این کالا هیچ‌جا (خرید، انبار، پروژه، فروش) استفاده نشده؛ برخلاف غیرفعال‌کردن، این دکمه کامل پاکش می‌کند.</span>
    <button type="submit" class="btn btn-soft btn-error btn-sm">حذف همیشگی</button>
</form>
{% endif %}
```

### گام ۹ — لینک‌های دسترسی

**`templates/finance/partials/accounting_nav.html`**: بعد از لینک «حرکات انبار» اضافه کن:
```html
<a href="{% url 'inventory:warehouse_list' %}" class="btn btn-sm btn-soft">{% icon "package" "w-4 h-4" %} انبارها</a>
<a href="{% url 'inventory:stock_transfer_new' %}" class="btn btn-sm btn-soft">{% icon "arrow-left-right" "w-4 h-4" %} انتقال بین انبارها</a>
```

**`templates/projects/technician_home.html`**: داخل بلوک `{% if can_manage_inventory %}` بعد از لینک «کالای جدید» اضافه کن:
```html
<a href="{% url 'inventory:warehouse_list' %}" class="btn btn-soft btn-sm">{% icon "package" "w-4 h-4" %} انبارها</a>
<a href="{% url 'inventory:stock_transfer_new' %}" class="btn btn-soft btn-sm">{% icon "arrow-left-right" "w-4 h-4" %} انتقال بین انبارها</a>
```

**`templates/dashboard/overview.html`**: در ردیف دکمه‌های بالای صفحه (کنار «ثبت خرید») اضافه کن:
```html
<a href="{% url 'inventory:warehouse_list' %}" class="btn btn-soft btn-sm">{% icon "package" "w-4 h-4" %} انبارها</a>
<a href="{% url 'inventory:stock_transfer_new' %}" class="btn btn-soft btn-sm">{% icon "arrow-left-right" "w-4 h-4" %} انتقال بین انبارها</a>
```

---

### گام ۱۰ (اختیاری ولی ارزانه) — نمایش جدول‌های فروش در ادمین

در `inventory/admin.py` اضافه کن:
```python
from .models import Sale, SaleLine, SalePayment


class SaleLineInline(JalaliAdminMixin, TabularInline):
    model = SaleLine
    extra = 0


class SalePaymentInline(JalaliAdminMixin, TabularInline):
    model = SalePayment
    extra = 0


@admin.register(Sale)
class SaleAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'number', 'status', 'customer_name', 'customer_phone', 'jalali_sold_at')
    list_filter = ('status',)
    search_fields = ('number', 'customer_name', 'customer_phone')
    inlines = [SaleLineInline, SalePaymentInline]

    jalali_sold_at = jalali_column('sold_at', 'تاریخ فروش')
```

---

**گزارش بخواه:** فهرست فایل‌های تغییرکرده، `git diff --stat`، و تایید اینکه `pnpm run build` بدون خطا اجرا شده (چون JS تغییر کرده). بعد از merge یادت باشه که این بریف تست خودکار ندارد — دستی یک خرید دو‌ردیفی با دو انبار متفاوت، یک تعدیل با انبار مشخص، و یک انتقال بین دو انبار را امتحان کن.