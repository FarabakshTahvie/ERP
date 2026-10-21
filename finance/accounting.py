from datetime import date, datetime, time, timedelta
from decimal import Decimal

import jdatetime
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import (
    Case, Count, DecimalField, Exists, ExpressionWrapper, F, Max, OuterRef, Q, Subquery, Sum, Value, When
)
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from inventory.models import PurchaseLine, StockLot, StockMovement
from inventory.services import (
    low_stock_items_count, consume_stock, record_manual_stock_change,
    CHANGE_KIND_RETURN, CHANGE_KIND_ADJUST_INCREASE, _FA_TO_EN,
)
from projects.models import (
    Project, ProjectCost,
    ProjectServiceMaterial, ProjectStage, StageKind, StageUsage,
)
from projects.services import user_can_access_accounting, project_prices_editable
from .models import Invoice, InvoiceLine, Payment, AccountingEvent, ChequeEvent
from .services import (
    parse_amount, proof_error, prepare_receipt_file, PROOF_METHODS,
    add_manual_invoice_line, recalculate_invoice_paid_amount, counted_payments, clean_cheque_fields,
    cheque_soon_q,
)
from utils.utils import separate_digits

ZERO = Decimal("0")
QTY_EPS = Decimal("0.0001")
QTY_Q = Decimal("0.0001")
MONEY = DecimalField(max_digits=24, decimal_places=2)
VALUE = ExpressionWrapper(F("qty") * F("unit_cost"), output_field=MONEY)
LOT_VALUE = ExpressionWrapper(F("qty_remaining") * F("unit_cost"), output_field=MONEY)
SUPPLIER_VALUE = ExpressionWrapper(F("purchases__lines__qty") * F("purchases__lines__unit_cost"), output_field=MONEY)


def supplier_items(party):
    """چه چیزی از این تأمین‌کننده خریده‌ایم."""
    from catalog.models import Item
    labels = dict(Item.Unit.choices)
    rows = list(PurchaseLine.objects.filter(purchase__supplier=party)
                .values("item_id", "item__name", "item__unit")
                .annotate(qty_sum=Sum("qty"), total=Sum(VALUE), last_at=Max("purchase__purchased_at"),
                          n=Count("purchase", distinct=True))
                .order_by("-total"))
    for r in rows:
        r["unit_label"] = labels.get(r["item__unit"], "")
    return rows
MT, DIR = StockMovement.MovementType, StockMovement.Direction

PERIODS = (
    ("all", "همه‌ی زمان‌ها"),
    ("this_month", "این ماه"),
    ("last_month", "ماه قبل"),
    ("this_year", "امسال"),
)


# ---------- بازه‌ی زمانی (ماه/سال شمسی) ----------
def _first_day(y, m):
    return jdatetime.date(y, m, 1).togregorian()


def period_range(key, today=None):
    """(شروع، پایان‌ِ‌ غیرشامل) میلادی؛ (None, None) یعنی همه‌ی زمان‌ها."""
    j = jdatetime.date.fromgregorian(date=today or timezone.localdate())
    if key == "this_year":
        return _first_day(j.year, 1), _first_day(j.year + 1, 1)
    if key == "this_month":
        y, m = j.year, j.month
    elif key == "last_month":
        y, m = (j.year, j.month - 1) if j.month > 1 else (j.year - 1, 12)
    else:
        return None, None
    ny, nm = (y, m + 1) if m < 12 else (y + 1, 1)
    return _first_day(y, m), _first_day(ny, nm)


def _dt(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def _range_q(field, start, end, is_date=False):
    q = Q()
    if start:
        q &= Q(**{f"{field}__gte": start if is_date else _dt(start)})
    if end:
        q &= Q(**{f"{field}__lt": end if is_date else _dt(end)})
    return q


from .aging import debt_invoices

def _sum(qs, expr):
    return qs.aggregate(t=Coalesce(Sum(expr), Value(ZERO), output_field=MONEY))["t"]


def _remaining(qs):
    return _sum(qs, ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY))


# ---------- نمای کلی ----------
def accounting_overview(period_key="all", today=None):
    from projects.services import held_project_ids
    start, end = period_range(period_key, today)
    held = held_project_ids()
    invoices = Invoice.objects.exclude(status=Invoice.Status.CANCELLED).exclude(project_id__in=held)
    debts = debt_invoices(Invoice.objects.all())
    collected_qs = (
        counted_payments(Payment.objects.all())
        .exclude(invoice__project_id__in=held)
        .annotate(eff_at=Coalesce("paid_at", "approved_at", "created_at")).filter(_range_q("eff_at", start, end))
    )
    moves = StockMovement.objects.filter(_range_q("created_at", start, end))
    ct = ContentType.objects.get_for_model(Project)
    moves_linked_held = moves.exclude(related_content_type=ct, related_object_id__in=held)
    final_rows = list(projects_financial_queryset().filter(final_done=True).filter(_range_q("final_at", start, end)))
    return {
        "period": period_key, "start": start, "end": end,
        "sales": _sum(invoices.filter(_range_q("issue_date", start, end, is_date=True)), F("total_amount")),
        "collected": _sum(collected_qs, F("amount")),
        "receivable": _remaining(debts.exclude(project_id__in=held)),
        "held_receivable": _remaining(debts.filter(project_id__in=held)),
        "purchases": _sum(PurchaseLine.objects.filter(_range_q("purchase__purchased_at", start, end)), VALUE),
        "opening": _sum(moves.filter(movement_type=MT.OPENING), VALUE),
        "consumption": _sum(moves_linked_held.filter(movement_type=MT.OUT), VALUE),
        "consumption_unlinked": _sum(moves.filter(movement_type=MT.OUT, related_content_type__isnull=True), VALUE),
        "adjust_loss": _sum(moves_linked_held.filter(movement_type=MT.ADJUST, direction=DIR.OUT), VALUE),
        "adjust_gain": _sum(moves_linked_held.filter(movement_type=MT.ADJUST, direction=DIR.IN), VALUE),
        "returns": _sum(moves_linked_held.filter(movement_type=MT.RETURN), VALUE),
        "final_result": sum((p.net_result for p in final_rows), ZERO),
        "final_count": len(final_rows),
        "stock_value": _sum(StockLot.objects.all(), LOT_VALUE),
        "integrity": stock_integrity(),
    }


def attention_items():
    """فهرست «نیازمند اقدام»؛ فقط مواردی که تعدادشان صفر نیست."""
    out = []

    def add(label, count, url, level="warning"):
        if count:
            out.append({"label": label, "count": count, "url": url, "level": level})

    add("پرداخت منتظر تایید",
        Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY).count(),
        reverse("finance:payments_review"))
    add("چک نزدیک به سررسید یا گذشته از آن",
        Payment.objects.filter(cheque_soon_q()).count(),
        reverse("finance:payments_review") + "?py_f_cheque_soon=1&py_sort=cheque_due_date&py_dir=asc")
    add("پروژه‌ی تکمیل‌شده‌ی دارای مانده‌ی فاکتور",
        Invoice.objects.exclude(status=Invoice.Status.CANCELLED).filter(project__status=Project.Status.COMPLETED)
        .annotate(rem=ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY))
        .filter(rem__gt=0).count(),
        reverse("finance:accounting_projects") + "?ap_f_status=completed&ap_fmin_remaining=1", "error")
    add("کالای رو به اتمام", low_stock_items_count(), reverse("finance:accounting_inventory") + "?st_f_low=1", "info")
    return out


def final_review_queue(limit=20):
    "پروژه‌هایی که بازبینی نهایی‌شان باز است + آنچه جلوی تایید یا درستی حساب را می‌گیرد."
    stages = (ProjectStage.objects.filter(kind=StageKind.FINAL_REVIEW, status=ProjectStage.Status.IN_PROGRESS)
              .select_related("project").order_by("project__name")[:limit])
    rows = []
    for st in stages:
        p = st.project
        rows.append({
            "project": p,
            "unsettled": sum(1 for r in project_reconciliation(p) if r["status"] != "ok"),
        })
    return rows


def period_rows(count=14):
    """ماه‌های شمسی گذشته (جدیدترین اول): وضعیت قفل و تعداد پرداخت منتظر تایید همان ماه."""
    from core.models import PeriodLock
    from core.periods import current_ym, month_label
    from datetime import datetime, time
    from django.utils.timezone import make_aware, get_current_timezone
    y, m = current_ym()
    locked = {(l.year, l.month) for l in PeriodLock.objects.filter(is_locked=True)}
    rows = []
    tz = get_current_timezone()
    _dt = lambda d: make_aware(datetime.combine(d, time.min), tz)
    for _ in range(count):
        m -= 1
        if m < 1:
            y, m = y - 1, 12
        start = jdatetime.date(y, m, 1).togregorian()
        end = (jdatetime.date(y + 1, 1, 1) if m == 12 else jdatetime.date(y, m + 1, 1)).togregorian()
        pending = (Payment.objects.filter(status=Payment.Status.PENDING,
                                          created_at__gte=_dt(start), created_at__lt=_dt(end))
                   .exclude(method=Payment.Method.GATEWAY).count())
        rows.append({"year": y, "month": m, "label": month_label(y, m),
                     "locked": (y, m) in locked, "pending_count": pending})
    return rows



# ---------- مالی هر پروژه ----------
def projects_financial_queryset():
    """
    پروژه‌ها با: revenue (فاکتور غیرلغوشده)، paid، remaining، stock_out (مصرف و کسری وصل‌به‌پروژه)،
    stock_back (تعدیل افزایشی وصل‌به‌پروژه)، rec_costs (هزینه‌های ثبت‌شده)، planned_cost (بهای کالا طبق پیش‌فاکتور)،
    actual_cost = stock_out − stock_back + rec_costs ، profit = revenue − actual_cost.
    """
    ct = ContentType.objects.get_for_model(Project)

    def moves_sum(cond):
        qs = (StockMovement.objects.filter(cond, related_content_type=ct, related_object_id=OuterRef("pk"))
              .order_by().values("related_object_id").annotate(t=Sum(VALUE)).values("t"))
        return Coalesce(Subquery(qs, output_field=MONEY), Value(ZERO), output_field=MONEY)

    cost_qs = (ProjectCost.objects.filter(project=OuterRef("pk")).order_by().values("project")
               .annotate(t=Sum("amount")).values("t"))
    final_qs = ProjectStage.objects.filter(project=OuterRef("pk"), kind=StageKind.FINAL_REVIEW, status=ProjectStage.Status.DONE)

    return (
        Project.objects.select_related("owner", "partner")
        .annotate(
            revenue=Coalesce(
                Case(When(invoice__status=Invoice.Status.CANCELLED, then=Value(ZERO)),
                     default=F("invoice__total_amount"), output_field=MONEY),
                Value(ZERO), output_field=MONEY),
            paid=Coalesce(F("invoice__paid_amount"), Value(ZERO), output_field=MONEY),
            stock_out=moves_sum(Q(movement_type=MT.OUT) | Q(movement_type=MT.ADJUST, direction=DIR.OUT)),
            stock_back=moves_sum(Q(movement_type__in=(MT.ADJUST, MT.RETURN), direction=DIR.IN)),
            rec_costs=Coalesce(Subquery(cost_qs, output_field=MONEY), Value(ZERO), output_field=MONEY),
            final_done=Exists(final_qs),
            final_at=Subquery(final_qs.values("completed_at")[:1]),
        )
        .annotate(
            remaining=ExpressionWrapper(F("revenue") - F("paid"), output_field=MONEY),
            actual_cost=ExpressionWrapper(F("stock_out") - F("stock_back") + F("rec_costs"), output_field=MONEY),
        )
        .annotate(net_result=ExpressionWrapper(F("revenue") - F("actual_cost"), output_field=MONEY))
    )


def project_movements(project, limit=200):
    ct = ContentType.objects.get_for_model(Project)
    moves = list(StockMovement.objects.filter(related_content_type=ct, related_object_id=project.pk)
                 .select_related("item", "created_by").order_by("-created_at", "-id")[:limit])
    for m in moves:
        m.line_value = (m.qty * m.unit_cost).quantize(Decimal("1"))
        m.line_total = m.line_value
    return moves


def project_reconciliation(project):
    """
    مغایرت مواد هر پروژه (فقط مقدار؛ بدون قضاوت مالی). فقط کالایی می‌آید که تکنسین‌ها در مرحله‌ها مصرفش
    را ثبت کرده یا برایش خروجی از انبار ثبت شده؛ کالای پیش‌فاکتورِ بی‌مصرف نمی‌آید.
    expected (مصرف نهایی پیشنهادی):
      ۱) کالا مصرف ثبت‌شده‌ی مرحله دارد ← جمع مصرف مرحله‌ها (by_stage به تفکیک مرحله)؛
      ۲) وگرنه (فقط دستی کم شده) ← همان خالص کسرشده.
    unsettled = expected − net_out
    """
    ct = ContentType.objects.get_for_model(Project)
    planned = {}
    for m in ProjectServiceMaterial.objects.filter(service_line__project=project):
        planned[m.item_id] = planned.get(m.item_id, ZERO) + m.qty
    rows = {}

    def row(item):
        return rows.setdefault(item.pk, {
            "item": item, "planned": planned.get(item.pk, ZERO), "used": ZERO, "by_stage": [],
            "out_qty": ZERO, "back_qty": ZERO, "value": ZERO,
        })

    for u in (StageUsage.objects.filter(stage__project=project).select_related("item", "stage")
              .order_by("stage__order", "pk")):
        r = row(u.item)
        r["used"] += u.qty
        r["by_stage"].append({"stage": u.stage, "qty": u.qty})
    for mv in StockMovement.objects.filter(related_content_type=ct, related_object_id=project.pk).select_related("item"):
        r, val = row(mv.item), mv.qty * mv.unit_cost
        if mv.direction == DIR.OUT and mv.movement_type in (MT.OUT, MT.ADJUST):
            r["out_qty"] += mv.qty
            r["value"] += val
        elif mv.direction == DIR.IN and mv.movement_type in (MT.ADJUST, MT.RETURN):
            r["back_qty"] += mv.qty
            r["value"] -= val

    result = []
    for r in rows.values():
        r["net_out"] = r["out_qty"] - r["back_qty"]
        r["unit_label"] = r["item"].get_unit_display()
        r["stock"] = r["item"].current_stock
        if r["used"] > 0:
            r["basis"], r["expected"] = "usage", r["used"]
        else:
            r["basis"], r["expected"] = "manual", r["net_out"]
        r["unsettled"] = r["expected"] - r["net_out"]
        r["shortfall"] = max(r["unsettled"] - r["stock"], ZERO)   # آنچه انبار الان نمی‌تواند پوشش دهد
        r["stock_short"] = r["shortfall"] > 0
        r["shortfall_str"] = format(r["shortfall"].quantize(QTY_Q).normalize(), "f")
        r["status"] = "ok" if abs(r["unsettled"]) <= QTY_EPS else ("short" if r["unsettled"] > 0 else "over")
        r["unit"] = (r["value"] / r["net_out"]) if r["net_out"] > 0 else Decimal(r["item"].moving_average_cost or 0)
        r["expected_input"] = format(r["expected"].quantize(QTY_Q).normalize(), "f")
        r["net_str"] = format(r["net_out"].quantize(QTY_Q).normalize(), "f")
        r["unit_str"] = format(Decimal(r["unit"]).quantize(Decimal("1")), "f")
        result.append(r)
    result.sort(key=lambda r: r["item"].name)
    return result


def project_pnl(p):
    """فقط اعداد؛ هیچ پیش‌بینی یا قضاوتی ندارد. «موقت» تا تایید نهایی."""
    stock_cost = p.stock_out - p.stock_back
    final = bool(p.final_done)
    return {
        "revenue": p.revenue, "collected": p.paid, "remaining": p.remaining,
        "stock_cost": stock_cost, "recorded_costs": p.rec_costs,
        "result": p.revenue - stock_cost - p.rec_costs,
        "state": "final" if final else "provisional",
        "state_label": "بعد از تسویه" if final else "موقت",
    }


def stock_integrity():
    """هویت ثابت: ورودی‌ها − خروجی‌ها = ارزش لات‌ها. اختلاف یعنی لاتی بدون حرکت یا حرکتی بدون لات."""
    in_val = _sum(StockMovement.objects.filter(direction=DIR.IN), VALUE)
    out_val = _sum(StockMovement.objects.filter(direction=DIR.OUT), VALUE)
    stock_val = _sum(StockLot.objects.all(), LOT_VALUE)
    unclassified = _sum(StockMovement.objects.filter(movement_type=MT.IN, lot__purchase_line__isnull=True), VALUE)
    return {"in": in_val, "out": out_val, "stock": stock_val, "diff": in_val - out_val - stock_val,
            "unclassified_in": unclassified}


def proforma_queue(limit=20):
    return list(ProjectStage.objects.filter(kind=StageKind.PROFORMA, status=ProjectStage.Status.IN_PROGRESS)
                .select_related("project").order_by("project__name")[:limit])


def parse_qty(raw, label="مقدار"):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace("٫", ".")
    try:
        value = Decimal(text)
    except Exception:
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    if not value.is_finite() or value < 0 or value > Decimal("9999999"):
        raise ValueError(f"{label} باید عددی نامنفی و معقول باشد.")
    return value.quantize(QTY_Q)


def log_event(*, kind, text, actor, project=None, amount=None):
    return AccountingEvent.objects.create(
        project=project, kind=kind, text=(text or "")[:500],
        amount=amount, actor=actor if getattr(actor, "pk", None) else None)


@transaction.atomic
def settle_project_materials(*, project, final_qtys, reasons, actor, cover=frozenset()):
    """
    ثبت مصرف نهایی مواد پروژه. final_qtys: {item_id: مصرف نهایی خالص}، reasons: {item_id: دلیل}.
    کالایی که مقدارش نیامده یا خالی است همان پیشنهاد سیستم را می‌گیرد؛ تغییر نسبت به پیشنهاد دلیل اجباری دارد.
    مصرف مرحله‌ها از قبل از انبار کم شده؛ اینجا فقط تفاوت مصرف نهایی با کسرشده‌ی خالص کم می‌شود (FIFO)
    یا با نوع RETURN برمی‌گردد.
    اگر موجودی برای آن تفاوت کم بود: بدون cover خطا. با cover (مجموعه‌ی id کالا) مقدار کسری با تعدیل افزایشی
    (بدون وصل به پروژه) ثبت و بعد مصرف می‌شود.
    """
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند مصرف مواد را تسویه کند.")
    project = Project.objects.select_for_update().get(pk=project.pk)
    applied, covered, total = [], [], ZERO
    for r in project_reconciliation(project):
        item = r["item"]
        suggested = r["expected"].quantize(QTY_Q)
        final = final_qtys.get(item.pk, suggested)
        reason = (reasons.get(item.pk) or "").strip()
        if final != suggested and not reason:
            raise ValueError(f"برای «{item.name}» دلیل تغییر مقدار را بنویسید.")
        delta = final - r["net_out"].quantize(QTY_Q)
        if abs(delta) <= QTY_EPS:
            continue
        note = f"تسویه‌ی نهایی مصرف مواد پروژه — {reason or 'مطابق محاسبه‌ی سیستم'}"
        if delta > 0:
            missing = delta - Decimal(item.current_stock)
            if missing > QTY_EPS:
                missing = missing.quantize(QTY_Q)
                missing_text = format(missing.normalize(), "f")
                if item.pk not in cover:
                    raise ValueError(
                        f"موجودی «{item.name}» به اندازه‌ی {missing_text} کمتر از مصرف است. "
                        "موجودی را کامل کنید، یا کسری را ثبت کنید، یا مصرف نهایی را اصلاح کنید.")
                try:
                    record_manual_stock_change(
                        item=item, kind=CHANGE_KIND_ADJUST_INCREASE, qty_raw=missing_text, user=actor,
                        notes=f"کسری ثبت‌نشده‌ی انبار؛ مصرف پروژه‌ی «{project.name}» — {reason or 'مطابق محاسبه‌ی سیستم'}"[:255])
                except ValueError as e:
                    raise ValueError(f"«{item.name}»: {e}")
                covered.append((item.name, missing))
            consume_stock(item=item, qty=delta, user=actor, related_object=project, notes=note)
            total += delta * r["unit"]
        else:
            record_manual_stock_change(item=item, kind=CHANGE_KIND_RETURN, qty_raw=str(-delta), notes=note,
                                       user=actor, related_object=project)
            total -= (-delta) * r["unit"]
        applied.append((item.name, delta, reason))
    if applied:
        extra = ""
        if covered:
            extra = "؛ کسری انبار ثبت‌شده با تعدیل افزایشی: " + "، ".join(
                f"{n} ({format(q.normalize(), 'f')})" for n, q in covered)
        log_event(kind=AccountingEvent.Kind.SETTLEMENT, project=project, actor=actor,
                  amount=total.quantize(Decimal("1")),
                  text="تسویه‌ی مصرف: " + "؛ ".join(
                      f"{n} ({d:+f}{('، ' + rs) if rs else ''})" for n, d, rs in applied) + extra)
    return applied


@transaction.atomic
def add_invoice_adjustment(*, invoice, title, amount_raw, kind, reason, actor):
    """ردیف دستی فاکتور بعد از قفل قیمت‌ها. kind: increase | decrease. دلیل داخلی اجباری است."""
    from core.periods import assert_open
    assert_open(invoice.issue_date, "اصلاح فاکتور")
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند فاکتور را اصلاح کند.")
    title, reason = (title or "").strip(), (reason or "").strip()
    if not title:
        raise ValueError("عنوان ردیف را بنویسید.")
    if not reason:
        raise ValueError("دلیل اصلاح را بنویسید.")
    if kind not in ("increase", "decrease"):
        raise ValueError("نوع اصلاح معتبر انتخاب کنید.")
    invoice = Invoice.objects.select_for_update(of=("self",)).select_related("project").get(pk=invoice.pk)
    if project_prices_editable(invoice.project):
        raise ValueError("قیمت‌ها هنوز قابل ویرایش‌اند؛ از ویرایشگر پیش‌فاکتور استفاده کنید.")
    amount = parse_amount(amount_raw)
    signed = amount if kind == "increase" else -amount
    if invoice.total_amount + signed < invoice.paid_amount:
        raise ValueError("جمع فاکتور نمی‌تواند از مبلغ دریافتی کمتر شود.")
    add_manual_invoice_line(invoice, title=title, amount=signed, actor=actor,
                            line_type=InvoiceLine.LineType.EXTRA if signed > 0 else InvoiceLine.LineType.DISCOUNT)
    invoice.refresh_from_db()
    recalculate_invoice_paid_amount(invoice)
    log_event(kind=AccountingEvent.Kind.INVOICE_LINE, project=invoice.project, actor=actor, amount=signed,
              text=f"{title} — {reason}")
    # TODO(پیامک invoice_updated): ردیف دستی به فاکتور اضافه شد؛ به مشتری دارای حساب با notify_users.


ACCOUNTANT_PAYMENT_METHODS = (
    Payment.Method.CARD_TO_CARD, Payment.Method.RECEIPT, Payment.Method.CHEQUE, Payment.Method.CASH,
)


@transaction.atomic
def record_accountant_payment(*, invoice, method, amount_raw, paid_date, reference_number, note,
                              receipt_file, cheque_number="", cheque_bank="", cheque_due_date=None, actor):
    """پرداخت واقعی توسط حسابدار؛ چون خودش تاییدکننده است مستقیم «تاییدشده» ثبت می‌شود.
    چک: شناسه‌ی صیادی و سررسید الزامی؛ وضعیت «تحویل گرفته‌شده»."""
    from core.periods import assert_open
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند پرداخت ثبت کند.")
    if paid_date:
        assert_open(paid_date, "پرداخت")
        if paid_date > timezone.localdate():
            raise ValueError("تاریخ پرداخت نمی‌تواند در آینده باشد.")
    if method not in ACCOUNTANT_PAYMENT_METHODS:
        raise ValueError("روش پرداخت معتبر انتخاب کنید.")
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("فاکتور لغوشده است.")
    amount = parse_amount(amount_raw)
    if amount > invoice.remaining_amount:
        raise ValueError(f"مبلغ از مانده‌ی فاکتور ({separate_digits(invoice.remaining_amount)} تومان) بیشتر است.")
    reference_number, note = (reference_number or "").strip(), (note or "").strip()
    if method == Payment.Method.CASH:
        if not note:
            raise ValueError("برای پرداخت نقدی، توضیح بنویسید.")
    else:
        error = proof_error(method, has_file=bool(receipt_file), reference=reference_number)
        if error:
            raise ValueError(error)
    if method == Payment.Method.CHEQUE:
        cheque_number, cheque_bank = clean_cheque_fields(number=cheque_number, bank=cheque_bank, due_date=cheque_due_date)
    if Payment.objects.filter(invoice=invoice, method=method, amount=amount, reference_number=reference_number,
                              created_at__gte=timezone.now() - timezone.timedelta(seconds=60)).exists():
        raise ValueError("همین پرداخت لحظاتی پیش ثبت شده است.")
    kwargs = dict(
        invoice=invoice, method=method, amount=amount, claimed_amount=amount, status=Payment.Status.APPROVED,
        approved_by=actor, approved_at=timezone.now(), paid_at=_dt(paid_date) if paid_date else timezone.now(),
        reference_number=reference_number, note=note,
    )
    if receipt_file:
        kwargs["receipt_file"] = prepare_receipt_file(receipt_file)
    if method == Payment.Method.CHEQUE:
        kwargs.update(cheque_number=cheque_number, cheque_bank=cheque_bank, cheque_due_date=cheque_due_date,
                      cheque_status=Payment.ChequeStatus.RECEIVED)
    payment = Payment.objects.create(**kwargs)
    if method == Payment.Method.CHEQUE:
        ChequeEvent.objects.create(payment=payment, from_status="", to_status=Payment.ChequeStatus.RECEIVED,
                                   note="ثبت توسط حسابدار", actor=actor)
    log_event(kind=AccountingEvent.Kind.PAYMENT, project=invoice.project, actor=actor, amount=amount,
              text=f"پرداخت {payment.get_method_display()} ثبت شد")
    return payment