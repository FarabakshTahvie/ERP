import re
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.capabilities import can
from utils.utils import monthly_prefix, next_monthly_code, normalize_phone, separate_digits, to_latin_digits
from .models import Sale, SaleEvent, SaleLine, SalePayment, StockMovement, Warehouse
from .services import assert_stockable, consume_stock, get_active_item, parse_decimal_input

BAD_LINES = "کالاهای فروش درست ارسال نشد؛ صفحه را دوباره باز کنید."
MAX_LINES = 50
MAX_QTY = Decimal("9999999")
MAX_PRICE = Decimal("1000000000000")
QTY_Q = Decimal("0.0001")
NAME_MAX = 150
ZERO = Decimal("0")
MONEY = DecimalField(max_digits=24, decimal_places=2)
STATUS_VARIANT = {"registered": "warning", "delivered": "success", "cancelled": "error"}


# ---------- ورودی‌ها ----------
def clean_customer(name, phone):
    name = " ".join(str(name or "").split())
    if len(name) > NAME_MAX:
        raise ValueError(f"نام مشتری نباید بیش از {NAME_MAX} نویسه باشد.")
    phone = normalize_phone(phone)
    if phone and not re.fullmatch(r"0\d{10}", phone):
        raise ValueError("شماره‌ی مشتری را ۱۱ رقمی بنویسید، مثل ۰۹۱۲۳۴۵۶۷۸۹.")
    return name, phone


def _short(raw, limit, label):
    text = " ".join(str(raw or "").split())
    if len(text) > limit:
        raise ValueError(f"{label} نباید بیش از {limit} نویسه باشد.")
    return text


def _clean_notes(raw):
    return _short(raw, 255, "توضیح")


def _clean_reason(raw):
    text = _short(raw, 300, "دلیل")
    if not text:
        raise ValueError("دلیل را بنویسید.")
    return text


def _money(raw, label="مبلغ"):
    text = to_latin_digits(raw).strip().replace(",", "").replace("٬", "").replace(" ", "")
    if not re.fullmatch(r"\d{1,12}", text) or int(text) <= 0:
        raise ValueError(f"{label} باید عدد صحیح و بزرگ‌تر از صفر (به تومان) باشد.")
    return Decimal(int(text))


def _get_warehouse(raw):
    try:
        return Warehouse.objects.get(pk=int(to_latin_digits(raw).strip()))
    except (TypeError, ValueError, Warehouse.DoesNotExist):
        raise ValueError("انبار را از فهرست انتخاب کنید.")


def _check_method(method):
    if method not in SalePayment.Method.values:
        raise ValueError("روش پرداخت را انتخاب کنید.")
    return method


def _paid_day(value):
    from core.periods import assert_open
    day = value or timezone.localdate()
    if day > timezone.localdate():
        raise ValueError("تاریخ پرداخت نمی‌تواند در آینده باشد.")
    assert_open(day, "پرداخت فروش")
    return day


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
        total = (qty * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if total <= 0:
            raise ValueError(f"جمع «{item.name}» صفر می‌شود؛ مقدار یا قیمت را بزرگ‌تر بنویسید.")
        lines.append({"item": item, "qty": qty, "unit_price": price.to_integral_value(), "total": total})
    return lines


def _save_lines(sale, lines):
    SaleLine.objects.bulk_create([
        SaleLine(sale=sale, item=l["item"], qty=l["qty"], unit_price=l["unit_price"], total=l["total"])
        for l in lines])


# ---------- دسترسی و قفل ----------
def _require_sales(actor):
    if not can(actor, "sales.create"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند فروش را ثبت یا ویرایش کند.")


def _require_accounting(actor):
    if not can(actor, "accounting.access"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند پرداخت فروش را ثبت کند.")


def _locked(sale_or_pk):
    pk = getattr(sale_or_pk, "pk", sale_or_pk)
    sale = Sale.objects.select_for_update(of=("self",)).select_related("warehouse").filter(pk=pk).first()
    if sale is None:
        raise ValueError("این فروش پیدا نشد.")
    return sale


def _locked_payment(payment_id):
    sale_id = SalePayment.objects.filter(pk=payment_id).values_list("sale_id", flat=True).first()
    if sale_id is None:
        raise ValueError("این پرداخت پیدا نشد.")
    sale = _locked(sale_id)
    payment = sale.payments.filter(pk=payment_id).first()
    if payment is None:
        raise ValueError("این پرداخت پیدا نشد.")
    return sale, payment


def _log(sale, actor, text, amount=None):
    SaleEvent.objects.create(sale=sale, actor=actor if getattr(actor, "pk", None) else None,
                             text=text[:500], amount=amount)


def _sale_total(sale):
    return sale.lines.aggregate(t=Sum("total"))["t"] or ZERO


def _sale_paid(sale):
    return sale.payments.aggregate(t=Sum("amount"))["t"] or ZERO


def _new_number():
    return next_monthly_code(Sale.objects.all(), "number", monthly_prefix("S"))


# ---------- خواندن (تنها منبع جمع، دریافتی و مانده) ----------
def sales_queryset():
    """همه‌ی جدول‌ها، آمار و صفحه‌های فروش از همین می‌خوانند: total، paid، remaining."""
    lines = SaleLine.objects.filter(sale=OuterRef("pk")).order_by().values("sale")
    pays = SalePayment.objects.filter(sale=OuterRef("pk")).order_by().values("sale")
    zero = Value(ZERO, output_field=MONEY)
    total = Coalesce(Subquery(lines.annotate(t=Sum("total")).values("t"), output_field=MONEY), zero)
    paid = Coalesce(Subquery(pays.annotate(t=Sum("amount")).values("t"), output_field=MONEY), zero)
    return (Sale.objects.select_related("warehouse")
            .annotate(total=total, paid=paid)
            .annotate(remaining=ExpressionWrapper(F("total") - F("paid"), output_field=MONEY))
            .order_by("-sold_at", "-id"))


def sales_stats(qs=None):
    """همه‌ی زمان‌ها؛ فروش لغوشده نمی‌آید."""
    qs = sales_queryset() if qs is None else qs
    rows = list(qs.exclude(status=Sale.Status.CANCELLED).values("status", "total", "paid"))
    total = sum((r["total"] for r in rows), ZERO)
    paid = sum((r["paid"] for r in rows), ZERO)
    return {"count": len(rows), "total": total, "paid": paid, "remaining": total - paid,
            "waiting": sum(1 for r in rows if r["status"] == Sale.Status.REGISTERED)}


def customer_q(sale):
    """کلید مشتری: شماره؛ اگر شماره نداشت نام."""
    if sale.customer_phone:
        return Q(customer_phone=sale.customer_phone)
    return Q(customer_phone="", customer_name=sale.customer_name)


def customer_sales_qs(sale):
    return sales_queryset().filter(customer_q(sale))


def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def period_numbers(start=None, end=None):
    """مرکز حسابداری. start/end = تاریخ میلادی (انتها غیرشامل) یا None = همه‌ی زمان‌ها. فروش لغوشده نمی‌آید.
    sales: جمع فروش‌هایی که زمان ثبتشان در بازه است؛ collected: پرداخت‌هایی که تاریخ پرداختشان در بازه است؛
    remaining: مانده‌ی همه‌ی زمان‌ها (به بازه وابسته نیست)."""
    qs = sales_queryset().exclude(status=Sale.Status.CANCELLED)
    paid = SalePayment.objects.exclude(sale__status=Sale.Status.CANCELLED)
    if start:
        qs, paid = qs.filter(sold_at__gte=_day_start(start)), paid.filter(paid_date__gte=start)
    if end:
        qs, paid = qs.filter(sold_at__lt=_day_start(end)), paid.filter(paid_date__lt=end)
    return {
        "sales": sum(qs.values_list("total", flat=True), ZERO),
        "collected": paid.aggregate(t=Coalesce(Sum("amount"), Value(ZERO), output_field=MONEY))["t"],
        "remaining": sales_stats()["remaining"],
    }


# ---------- ثبت، ویرایش، تحویل، لغو ----------
@transaction.atomic
def create_sale(*, actor, lines_raw, warehouse_id, customer_name="", customer_phone="", notes="",
                pay_amount_raw="", pay_method=""):
    """فقط سند می‌سازد؛ موجودی کم نمی‌شود. اگر pay_amount_raw داده شود یک پرداخت (امروز) هم ثبت می‌شود."""
    _require_sales(actor)
    lines = _clean_lines(lines_raw)
    warehouse = _get_warehouse(warehouse_id)
    name, phone = clean_customer(customer_name, customer_phone)
    notes = _clean_notes(notes)
    total = sum((l["total"] for l in lines), ZERO)
    paying = bool(str(pay_amount_raw or "").strip())
    if paying:
        _require_accounting(actor)
        amount = _money(pay_amount_raw, "مبلغ دریافتی")
        if amount > total:
            raise ValueError("مبلغ دریافتی از جمع فروش بیشتر است.")
        method = _check_method(pay_method or SalePayment.Method.CASH)
    for attempt in range(5):
        try:
            with transaction.atomic():
                sale = Sale.objects.create(number=_new_number(), warehouse=warehouse, sold_at=timezone.now(),
                                           customer_name=name, customer_phone=phone, notes=notes,
                                           created_by=actor)
            break
        except IntegrityError:
            if attempt == 4:
                raise
    _save_lines(sale, lines)
    _log(sale, actor, f"ثبت شد: {len(lines)} قلم؛ بعد از تحویل از «{warehouse.name}» کم می‌شود", total)
    if paying:
        SalePayment.objects.create(sale=sale, method=method, amount=amount, paid_date=timezone.localdate(),
                                   created_by=actor)
        _log(sale, actor, "دریافتی هنگام ثبت", amount)
    return sale


@transaction.atomic
def update_sale(sale, *, actor, customer_name, customer_phone, notes, lines_raw=None, warehouse_id=None):
    """قبل از تحویل همه‌چیز قابل ویرایش است. بعد از تحویل فقط مشتری و توضیح (lines_raw و warehouse_id باید None باشند).
    lines_raw=None یعنی اقلام را دست نزن."""
    _require_sales(actor)
    sale = _locked(sale)
    if sale.status == Sale.Status.CANCELLED:
        raise ValueError("فروش لغوشده قابل ویرایش نیست.")
    name, phone = clean_customer(customer_name, customer_phone)
    notes = _clean_notes(notes)
    wants_wh = warehouse_id not in (None, "")
    changes = []
    if sale.status == Sale.Status.DELIVERED:
        if lines_raw is not None or wants_wh:
            raise ValueError("بعد از تحویل فقط مشتری، توضیح و پرداخت‌ها قابل ویرایش است.")
    else:
        if lines_raw is not None:
            lines = _clean_lines(lines_raw)
            if sum((l["total"] for l in lines), ZERO) < _sale_paid(sale):
                raise ValueError("جمع فروش نمی‌تواند از مبلغ دریافتی کمتر شود.")
            sale.lines.all().delete()
            _save_lines(sale, lines)
            changes.append("اقلام")
        if wants_wh:
            warehouse = _get_warehouse(warehouse_id)
            if warehouse.pk != sale.warehouse_id:
                sale.warehouse = warehouse
                changes.append("انبار")
    if (name, phone) != (sale.customer_name, sale.customer_phone):
        sale.customer_name, sale.customer_phone = name, phone
        changes.append("مشتری")
    if notes != sale.notes:
        sale.notes = notes
        changes.append("توضیح")
    if not changes:
        raise ValueError("تغییری ثبت نشد.")
    sale.save()
    _log(sale, actor, "ویرایش: " + "، ".join(changes))
    return sale


@transaction.atomic
def deliver_sale(sale, *, actor):
    """تحویل: اقلام به روش FIFO از انبارِ همین فروش کم می‌شوند. اگر موجودی یک قلم کم باشد هیچ‌چیز ثبت نمی‌شود."""
    _require_sales(actor)
    sale = _locked(sale)
    if sale.status != Sale.Status.REGISTERED:
        raise ValueError("فقط فروش «ثبت‌شده» تحویل داده می‌شود.")
    if sale.warehouse_id is None:
        raise ValueError("برای این فروش انبار مشخص نشده؛ ابتدا ویرایش کنید.")
    who = sale.customer_name or sale.customer_phone or "بدون نام"
    for line in sale.lines.select_related("item").order_by("pk"):
        assert_stockable(line.item)
        used = consume_stock(item=line.item, qty=line.qty, user=actor, related_object=sale,
                             notes=f"فروش {sale.number} به {who}"[:255],
                             movement_type=StockMovement.MovementType.SALE, warehouse=sale.warehouse)
        cost = sum((take * unit for _lot, take, unit in used), ZERO)
        SaleLine.objects.filter(pk=line.pk).update(cost_total=cost.quantize(Decimal("1")))
    sale.status, sale.delivered_at, sale.delivered_by = Sale.Status.DELIVERED, timezone.now(), actor
    sale.save(update_fields=["status", "delivered_at", "delivered_by", "updated_at"])
    _log(sale, actor, f"تحویل شد؛ اقلام از «{sale.warehouse.name}» کم شد")
    return sale


@transaction.atomic
def cancel_sale(sale, *, actor, reason):
    _require_sales(actor)
    reason = _clean_reason(reason)
    sale = _locked(sale)
    if sale.status != Sale.Status.REGISTERED:
        raise ValueError("فقط فروش «ثبت‌شده» لغو می‌شود؛ فروش تحویل‌شده حرکت انبار دارد.")
    if sale.payments.exists():
        raise ValueError("این فروش پرداخت دارد؛ ابتدا پرداخت‌ها را (با دلیل) حذف کنید.")
    sale.status = Sale.Status.CANCELLED
    sale.save(update_fields=["status", "updated_at"])
    _log(sale, actor, f"لغو شد — {reason}")
    return sale


# ---------- پرداخت‌ها ----------
def _payable(sale):
    if sale.status == Sale.Status.CANCELLED:
        raise ValueError("فروش لغوشده پرداخت ندارد.")


@transaction.atomic
def add_sale_payment(sale, *, actor, amount_raw, method, paid_date=None, reference="", note=""):
    _require_accounting(actor)
    sale = _locked(sale)
    _payable(sale)
    amount, method, day = _money(amount_raw), _check_method(method), _paid_day(paid_date)
    remaining = _sale_total(sale) - _sale_paid(sale)
    if amount > remaining:
        raise ValueError(f"مبلغ از مانده‌ی فروش ({separate_digits(remaining)} تومان) بیشتر است.")
    reference, note = _short(reference, 100, "شماره پیگیری"), _short(note, 255, "توضیح")
    if SalePayment.objects.filter(sale=sale, method=method, amount=amount, reference_number=reference,
                                  created_at__gte=timezone.now() - timedelta(seconds=60)).exists():
        raise ValueError("همین پرداخت لحظاتی پیش ثبت شده است.")
    payment = SalePayment.objects.create(sale=sale, method=method, amount=amount, paid_date=day,
                                         reference_number=reference, note=note, created_by=actor)
    _log(sale, actor, f"پرداخت {payment.get_method_display()} ثبت شد", amount)
    return payment


@transaction.atomic
def update_sale_payment(payment_id, *, actor, amount_raw, method, paid_date=None, reference="", note=""):
    from core.periods import assert_open
    _require_accounting(actor)
    sale, payment = _locked_payment(payment_id)
    _payable(sale)
    assert_open(payment.paid_date, "پرداخت فروش")
    amount, method, day = _money(amount_raw), _check_method(method), _paid_day(paid_date or payment.paid_date)
    others = _sale_paid(sale) - payment.amount
    if amount > _sale_total(sale) - others:
        raise ValueError("مبلغ از مانده‌ی فروش بیشتر است.")
    reference, note = _short(reference, 100, "شماره پیگیری"), _short(note, 255, "توضیح")
    if (amount, method, day, reference, note) == (payment.amount, payment.method, payment.paid_date,
                                                  payment.reference_number, payment.note):
        raise ValueError("تغییری ثبت نشد.")
    old = payment.amount
    payment.amount, payment.method, payment.paid_date = amount, method, day
    payment.reference_number, payment.note = reference, note
    payment.save()
    _log(sale, actor, f"پرداخت ویرایش شد: {separate_digits(old)} ← {separate_digits(amount)} تومان", amount)
    return payment


@transaction.atomic
def delete_sale_payment(payment_id, *, actor, reason):
    from core.periods import assert_open
    _require_accounting(actor)
    reason = _clean_reason(reason)
    sale, payment = _locked_payment(payment_id)
    _payable(sale)
    assert_open(payment.paid_date, "پرداخت فروش")
    amount = payment.amount
    payment.delete()
    _log(sale, actor, f"پرداخت حذف شد — {reason}", -amount)


# ---------- مشتری ----------
@transaction.atomic
def update_customer(*, actor, sale_id, name, phone):
    """مشتریِ این فروش را در همه‌ی فروش‌هایش اصلاح می‌کند (کلید مشتری: شماره، وگرنه نام)."""
    _require_sales(actor)
    base = Sale.objects.get(pk=sale_id)
    if not base.has_customer:
        raise ValueError("این فروش مشتری ندارد.")
    new_name, new_phone = clean_customer(name, phone)
    if not (new_name or new_phone):
        raise ValueError("نام یا شماره‌ی مشتری را بنویسید.")
    if (new_name, new_phone) == (base.customer_name, base.customer_phone):
        raise ValueError("تغییری ثبت نشد.")
    ids = list(Sale.objects.select_for_update().filter(customer_q(base)).values_list("pk", flat=True))
    old = f"{base.customer_name or '—'} / {base.customer_phone or '—'}"
    new = f"{new_name or '—'} / {new_phone or '—'}"
    Sale.objects.filter(pk__in=ids).update(customer_name=new_name, customer_phone=new_phone)
    SaleEvent.objects.bulk_create([SaleEvent(sale_id=i, actor=actor, text=f"اصلاح مشتری: {old} ← {new}")
                                   for i in ids])
    return len(ids)
