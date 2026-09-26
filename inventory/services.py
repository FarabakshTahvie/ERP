from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import F, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from catalog.models import Item
from core.models import Party
from .models import StockLot, StockMovement, Purchase, PurchaseLine, Warehouse

WAREHOUSE_KEEPER_SPECIALTY_NAME = "انباردار"

_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_decimal_input(raw, *, label="مقدار"):
    """رشته‌ی اعشاری (با ارقام فارسی/انگلیسی و جداکننده) را به Decimal مثبت تبدیل می‌کند؛ هر ایرادی ValueError فارسی می‌دهد."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace(" ", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{label} باید عددی بزرگ‌تر از صفر باشد.")
    return value


@transaction.atomic
def receive_stock(*, item, warehouse, qty, unit_cost, received_at, purchase_line=None,
                   movement_type=StockMovement.MovementType.IN, notes="", created_by=None):
    """
    ثبت لات جدید ورودی و به‌روزرسانی میانگین موزون قیمت کالا.
    movement_type پیش‌فرض IN (خرید) است؛ برای تعدیل افزایشی دستی (W3)، ADJUST پاس داده می‌شود.
    notes/created_by اختیاری‌اند تا خرید عادی (W2) دست‌نخورده بماند.
    """
    qty = Decimal(qty)
    unit_cost = Decimal(unit_cost)

    lot = StockLot.objects.create(
        item=item,
        warehouse=warehouse,
        purchase_line=purchase_line,
        qty_in=qty,
        qty_remaining=qty,
        unit_cost=unit_cost,
        received_at=received_at,
    )
    StockMovement.objects.create(
        item=item,
        lot=lot,
        movement_type=movement_type,
        qty=qty,
        unit_cost=unit_cost,
        notes=notes,
        created_by=created_by,
    )

    item_locked = item.__class__.objects.select_for_update().get(pk=item.pk)
    previous_qty = item_locked.current_stock - qty  # موجودی قبل از همین ورود
    if previous_qty > 0:
        new_average = ((previous_qty * item_locked.moving_average_cost) + (qty * unit_cost)) / (previous_qty + qty)
    else:
        new_average = unit_cost
    item_locked.moving_average_cost = new_average
    item_locked.save(update_fields=["moving_average_cost"])
    return lot


@transaction.atomic
def consume_stock(*, item, qty, user=None, related_object=None, notes="",
                   movement_type=StockMovement.MovementType.OUT):
    """
    مصرف به روش FIFO از قدیمی‌ترین لات. اگر موجودی کافی نبود، خطا می‌دهد.
    movement_type پیش‌فرض OUT (مصرف واقعی) است؛ برای تعدیل کاهشی دستی (W3)، ADJUST پاس داده می‌شود.
    """
    remaining = Decimal(qty)
    breakdown = []

    lots = StockLot.objects.select_for_update().filter(item=item, qty_remaining__gt=0).order_by("received_at")
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.qty_remaining, remaining)
        lot.qty_remaining = F("qty_remaining") - take
        lot.save(update_fields=["qty_remaining"])

        StockMovement.objects.create(
            item=item,
            lot=lot,
            movement_type=movement_type,
            qty=take,
            unit_cost=lot.unit_cost,
            related_object=related_object,
            created_by=user,
            notes=notes,
        )
        breakdown.append((lot, take, lot.unit_cost))
        remaining -= take

    if remaining > 0:
        raise ValueError(f"موجودی کالای «{item}» کافی نیست ({remaining} کسری).")

    _check_reorder_point(item)
    return breakdown


def _check_reorder_point(item):
    if item.reorder_point and item.current_stock <= item.reorder_point and item.responsible_user:
        pass
        # TODO(پوش هشدار موجودی کم): بعد از آماده شدن پوش/پیامک از کامنت خارج شود.


def user_can_manage_inventory(user):
    """
    دسترسی به بخش انبارداری: دقیقاً هم‌الگوی projects.services.user_can_create_projects.
    کاربر باید role=employee باشد و تخصص «انباردار» داشته باشد. مدیر استثنا نیست —
    مدیر از پنل ادمین (Item/StockLot/Purchase/Warehouse) استفاده می‌کند.
    """
    return (
        user.is_authenticated
        and getattr(user, "role", None) == "employee"
        and user.specialties.filter(name=WAREHOUSE_KEEPER_SPECIALTY_NAME).exists()
    )


def low_stock_items_count():
    """تعداد کالاهای فعالی که برایشان حد هشدار تعیین شده (reorder_point > 0) و موجودی به آن حد رسیده یا کمتر شده."""
    return (
        Item.objects.filter(is_active=True, reorder_point__gt=0)
        .annotate(
            stock=Coalesce(
                Sum("lots__qty_remaining"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=14, decimal_places=4),
            )
        )
        .filter(stock__lte=F("reorder_point"))
        .count()
    )


ALLOWED_INVOICE_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "pdf")
MAX_INVOICE_FILE_BYTES = 10 * 1024 * 1024


def _validate_invoice_file(invoice_file):
    if not invoice_file:
        return
    name = (getattr(invoice_file, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_INVOICE_EXTENSIONS:
        raise ValueError("فرمت فایل فاکتور خرید مجاز نیست؛ عکس (JPG، PNG، WEBP) یا PDF بارگذاری کنید.")
    if invoice_file.size > MAX_INVOICE_FILE_BYTES:
        raise ValueError("حجم فایل فاکتور خرید بیشتر از ۱۰ مگابایت است.")


def _clean_purchase_lines(raw_lines):
    cleaned = []
    for raw in (raw_lines or []):
        try:
            item_id = int(raw["id"])
            qty = Decimal(str(raw["qty"]))
            unit_cost = Decimal(str(raw["unit_cost"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValueError("اطلاعات ردیف‌های خرید نامعتبر است.")
        if not qty.is_finite() or not unit_cost.is_finite() or qty <= 0 or unit_cost <= 0:
            raise ValueError("در ردیف‌های خرید، مقدار و بهای واحد باید بزرگ‌تر از صفر باشند.")
        cleaned.append({"item_id": item_id, "qty": qty, "unit_cost": unit_cost})
    ids = {c["item_id"] for c in cleaned}
    if ids and Item.objects.filter(pk__in=ids, is_active=True).count() != len(ids):
        raise ValueError("یکی از کالاهای انتخاب‌شده در سیستم پیدا نشد یا غیرفعال است.")
    return cleaned


def _resolve_supplier_party(*, party_id=None, party_data=None):
    if party_id:
        return Party.objects.get(pk=party_id)
    if not party_data or not party_data.get("phone_number"):
        raise ValueError("اطلاعات تأمین‌کننده ناقص است.")
    if Party.objects.filter(phone_number=party_data["phone_number"]).exists():
        raise ValueError("طرف‌حسابی با این شماره از قبل وجود دارد؛ لطفاً همان را انتخاب کنید.")
    party_data = dict(party_data)
    party_data["is_supplier"] = True
    return Party.objects.create(**party_data)


@transaction.atomic
def create_purchase_from_form(*, supplier_party_id=None, supplier_party_data=None,
                              purchased_at, invoice_number="", notes="", invoice_file=None, lines_raw):
    lines = _clean_purchase_lines(lines_raw)
    if not lines:
        raise ValueError("حداقل یک ردیف کالا باید وارد شود.")

    warehouse = Warehouse.objects.filter(is_default=True).first()
    if not warehouse:
        raise ValueError("هیچ انبار پیش‌فرضی تعریف نشده است؛ ابتدا از پنل ادمین یک انبار با «انبار پیش‌فرض» فعال بسازید.")

    _validate_invoice_file(invoice_file)
    supplier = _resolve_supplier_party(party_id=supplier_party_id, party_data=supplier_party_data)

    purchase = Purchase.objects.create(
        supplier=supplier,
        invoice_number=(invoice_number or "").strip(),
        notes=(notes or "").strip(),
        purchased_at=purchased_at,
        invoice_file=invoice_file,
    )
    items_by_id = {i.pk: i for i in Item.objects.filter(pk__in=[l["item_id"] for l in lines])}
    for line in lines:
        item = items_by_id[line["item_id"]]
        purchase_line = PurchaseLine.objects.create(
            purchase=purchase, item=item, warehouse=warehouse,
            qty=line["qty"], unit_cost=line["unit_cost"],
        )
        receive_stock(
            item=item, warehouse=warehouse, qty=line["qty"], unit_cost=line["unit_cost"],
            received_at=purchased_at, purchase_line=purchase_line,
        )
    return purchase


CHANGE_KIND_CONSUME = "consume"
CHANGE_KIND_ADJUST_DECREASE = "adjust_decrease"
CHANGE_KIND_ADJUST_INCREASE = "adjust_increase"
CHANGE_KIND_CHOICES = (CHANGE_KIND_CONSUME, CHANGE_KIND_ADJUST_DECREASE, CHANGE_KIND_ADJUST_INCREASE)


@transaction.atomic
def record_manual_stock_change(*, item, kind, qty_raw, notes, user, unit_cost_raw=None):
    """
    تنها مسیر ثبت مصرف/تعدیل دستی موجودی (بدون پنل ادمین).
    - consume: مصرف واقعی -> consume_stock با movement_type=OUT.
    - adjust_decrease: تعدیل کاهشی (کسری/ضایعات) -> consume_stock با movement_type=ADJUST.
    - adjust_increase: تعدیل افزایشی (کشف موجودی) -> receive_stock با movement_type=ADJUST،
      در انبار پیش‌فرض، با بهای واحد وارد‌شده یا میانگین موزون فعلی کالا.
    دلیل (notes) همیشه اجباری است، دقیقاً هم‌الگوی advance_stage/reject_payment.
    """
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("ثبت دلیل الزامی است.")
    if kind not in CHANGE_KIND_CHOICES:
        raise ValueError("نوع تغییر معتبر انتخاب کنید.")

    qty = parse_decimal_input(qty_raw, label="مقدار")

    if kind == CHANGE_KIND_CONSUME:
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.OUT)
        return

    if kind == CHANGE_KIND_ADJUST_DECREASE:
        consume_stock(item=item, qty=qty, user=user, notes=notes, movement_type=StockMovement.MovementType.ADJUST)
        return

    # CHANGE_KIND_ADJUST_INCREASE
    warehouse = Warehouse.objects.filter(is_default=True).first()
    if not warehouse:
        raise ValueError("هیچ انبار پیش‌فرضی تعریف نشده است؛ ابتدا از پنل ادمین یک انبار با «انبار پیش‌فرض» فعال بسازید.")
    if str(unit_cost_raw or "").strip():
        unit_cost = parse_decimal_input(unit_cost_raw, label="بهای واحد")
    else:
        item.refresh_from_db()
        unit_cost = item.moving_average_cost
        if not unit_cost or unit_cost <= 0:
            raise ValueError("چون این کالا هنوز میانگین موزون قیمتی ندارد، بهای واحد را دستی وارد کنید.")
    receive_stock(
        item=item, warehouse=warehouse, qty=qty, unit_cost=unit_cost,
        received_at=timezone.now(), movement_type=StockMovement.MovementType.ADJUST,
        notes=notes, created_by=user,
    )
