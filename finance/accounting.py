from datetime import date, datetime, time, timedelta
from decimal import Decimal

import jdatetime
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import (
    Case, DecimalField, Exists, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum, Value, When
)
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from inventory.models import PurchaseLine, StockLot, StockMovement
from inventory.services import (
    low_stock_items_count, consume_stock, record_manual_stock_change,
    CHANGE_KIND_RETURN, _FA_TO_EN,
)
from projects.models import (
    ExtraShipment, InstallLine, PartRequest, Project, ProjectCost,
    ProjectServiceMaterial, ProjectStage, StageKind,
)
from projects.services import user_can_access_accounting, project_prices_editable
from .models import Invoice, InvoiceLine, Payment, AccountingEvent
from .services import (
    parse_amount, proof_error, prepare_receipt_file, PROOF_METHODS,
    add_manual_invoice_line, recalculate_invoice_paid_amount,
)
from utils.utils import separate_digits

ZERO = Decimal("0")
QTY_EPS = Decimal("0.0001")
QTY_Q = Decimal("0.0001")
MONEY = DecimalField(max_digits=24, decimal_places=2)
VALUE = ExpressionWrapper(F("qty") * F("unit_cost"), output_field=MONEY)
LOT_VALUE = ExpressionWrapper(F("qty_remaining") * F("unit_cost"), output_field=MONEY)
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


def _sum(qs, expr):
    return qs.aggregate(t=Coalesce(Sum(expr), Value(ZERO), output_field=MONEY))["t"]


# ---------- نمای کلی ----------
def accounting_overview(period_key="all", today=None):
    start, end = period_range(period_key, today)
    invoices = Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
    collected_qs = (
        Payment.objects.filter(status=Payment.Status.APPROVED).exclude(method=Payment.Method.CREDIT)
        .annotate(eff_at=Coalesce("approved_at", "created_at")).filter(_range_q("eff_at", start, end))
    )
    moves = StockMovement.objects.filter(_range_q("created_at", start, end))
    final_rows = list(projects_financial_queryset().filter(final_done=True).filter(_range_q("final_at", start, end)))
    return {
        "period": period_key, "start": start, "end": end,
        "sales": _sum(invoices.filter(_range_q("issue_date", start, end, is_date=True)), F("total_amount")),
        "collected": _sum(collected_qs, F("amount")),
        "receivable": _sum(invoices, ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY)),
        "purchases": _sum(PurchaseLine.objects.filter(_range_q("purchase__purchased_at", start, end)), VALUE),
        "opening": _sum(moves.filter(movement_type=MT.OPENING), VALUE),
        "consumption": _sum(moves.filter(movement_type=MT.OUT), VALUE),
        "consumption_unlinked": _sum(moves.filter(movement_type=MT.OUT, related_content_type__isnull=True), VALUE),
        "adjust_loss": _sum(moves.filter(movement_type=MT.ADJUST, direction=DIR.OUT), VALUE),
        "adjust_gain": _sum(moves.filter(movement_type=MT.ADJUST, direction=DIR.IN), VALUE),
        "returns": _sum(moves.filter(movement_type=MT.RETURN), VALUE),
        "credit_open": credit_open_total(),
        "final_profit": sum((p.profit for p in final_rows), ZERO),
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
    add("پرداخت اعتباری وصول‌نشده", len(credit_open_payments()),
        reverse("finance:payments_review") + "?py_f_method=credit&py_f_status=approved")
    add("درخواست قطعه‌ی بی‌پاسخ",
        PartRequest.objects.filter(status=PartRequest.Status.REQUESTED).count(), reverse("home") + "?tab=part_requests")
    add("قطعه‌ی اضافه‌ی ارسال‌شده بدون تعیین تکلیف",
        ExtraShipment.objects.filter(disposition=ExtraShipment.Disposition.PENDING).count(),
        reverse("finance:accounting_projects"), "error")
    add("پروژه‌ی تکمیل‌شده‌ی دارای مانده‌ی فاکتور",
        Invoice.objects.exclude(status=Invoice.Status.CANCELLED).filter(project__status=Project.Status.COMPLETED)
        .annotate(rem=ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY))
        .filter(rem__gt=0).count(),
        reverse("finance:accounting_projects") + "?ap_f_status=completed&ap_fmin_remaining=1", "error")
    add("کالای رو به اتمام", low_stock_items_count(), reverse("home") + "?tab=stock", "info")
    return out


def final_review_queue(limit=20):
    """پروژه‌هایی که بازبینی نهایی‌شان باز است + آنچه جلوی تایید یا درستی حساب را می‌گیرد."""
    stages = (ProjectStage.objects.filter(kind=StageKind.FINAL_REVIEW, status=ProjectStage.Status.IN_PROGRESS)
              .select_related("project").order_by("project__name")[:limit])
    rows = []
    for st in stages:
        p = st.project
        rows.append({
            "project": p,
            "pending_parts": PartRequest.objects.filter(project=p, status=PartRequest.Status.REQUESTED).count(),
            "pending_extras": ExtraShipment.objects.filter(project=p, disposition=ExtraShipment.Disposition.PENDING).count(),
            "unsettled": sum(1 for r in project_reconciliation(p) if r["status"] != "ok"),
        })
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
    plan_qs = (ProjectServiceMaterial.objects.filter(service_line__project=OuterRef("pk")).order_by()
               .values("service_line__project")
               .annotate(t=Sum(ExpressionWrapper(F("qty") * F("cost_snapshot"), output_field=MONEY))).values("t"))
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
            planned_cost=Coalesce(Subquery(plan_qs, output_field=MONEY), Value(ZERO), output_field=MONEY),
            final_done=Exists(final_qs),
            final_at=Subquery(final_qs.values("completed_at")[:1]),
        )
        .annotate(
            remaining=ExpressionWrapper(F("revenue") - F("paid"), output_field=MONEY),
            actual_cost=ExpressionWrapper(F("stock_out") - F("stock_back") + F("rec_costs"), output_field=MONEY),
        )
        .annotate(profit=ExpressionWrapper(F("revenue") - F("actual_cost"), output_field=MONEY))
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
    مغایرت مواد هر پروژه. قرارداد: «مقدار نصب‌شده» شامل قطعه‌های تحویلی از انبار هم هست.
    expected = (نصب‌شده؛ یا پیش‌فاکتور اگر نصب هنوز کامل ثبت نشده) + قطعه‌ی اضافه‌ی «مصرف شد»
    unsettled = expected − (خالص کسرشده از انبار برای این پروژه)
    variance = (بهای پیش‌بینی‌شده‌ی نهایی) − (بهای پیش‌فاکتور)؛ مثبت = زیان، منفی = سود
    """
    ct = ContentType.objects.get_for_model(Project)
    rows = {}

    def row(item):
        return rows.setdefault(item.pk, {
            "item": item, "planned": ZERO, "planned_cost": ZERO, "installed": ZERO, "install_lines": 0,
            "install_pending": 0, "parts_issued": ZERO, "extra_consumed": ZERO, "extra_pending": ZERO,
            "extra_returned": ZERO, "out_qty": ZERO, "back_qty": ZERO, "value": ZERO,
        })

    for m in ProjectServiceMaterial.objects.filter(service_line__project=project).select_related("item"):
        r = row(m.item)
        r["planned"] += m.qty
        r["planned_cost"] += m.qty * m.cost_snapshot
    for l in InstallLine.objects.filter(stage__project=project, kind=InstallLine.Kind.MATERIAL, item__isnull=False).select_related("item"):
        r = row(l.item)
        r["install_lines"] += 1
        if l.status == InstallLine.Status.PENDING:
            r["install_pending"] += 1
        elif l.status == InstallLine.Status.OK:
            r["installed"] += l.actual_qty or ZERO
    for p in PartRequest.objects.filter(project=project, status=PartRequest.Status.ISSUED).select_related("item"):
        row(p.item)["parts_issued"] += p.qty
    key = {ExtraShipment.Disposition.CONSUMED: "extra_consumed", ExtraShipment.Disposition.PENDING: "extra_pending",
           ExtraShipment.Disposition.RETURNED: "extra_returned"}
    for e in ExtraShipment.objects.filter(project=project).select_related("item"):
        row(e.item)[key[e.disposition]] += e.qty
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
        install_done = r["install_lines"] > 0 and r["install_pending"] == 0
        if install_done:
            target = r["installed"]
        elif r["planned"] == 0 and r["install_lines"] == 0:
            target = r["parts_issued"]
        else:
            target = r["planned"]
        r["basis"] = "install" if install_done else "plan"
        r["net_out"] = r["out_qty"] - r["back_qty"]
        r["expected"] = target + r["extra_consumed"]
        r["unsettled"] = r["expected"] - r["net_out"]
        r["status"] = "ok" if abs(r["unsettled"]) <= QTY_EPS else ("short" if r["unsettled"] > 0 else "over")
        r["unit"] = (r["value"] / r["net_out"]) if r["net_out"] > 0 else Decimal(r["item"].moving_average_cost or 0)
        r["projected_value"] = r["value"] + r["unsettled"] * r["unit"]
        r["variance"] = r["projected_value"] - r["planned_cost"]
        r["expected_input"] = format(r["expected"].quantize(QTY_Q).normalize(), "f")
        result.append(r)
    result.sort(key=lambda r: r["item"].name)
    return result


def project_pnl(p, recon):
    """p: ردیف projects_financial_queryset. سود موقت تا وقتی بازبینی نهایی تایید و همه‌ی اقلام تسویه نشده."""
    pending = sum((r["unsettled"] * r["unit"] for r in recon), ZERO).quantize(Decimal("1"))
    stock_cost = p.stock_out - p.stock_back
    settled = all(r["status"] == "ok" for r in recon)
    final = bool(p.final_done) and settled
    profit_booked = p.revenue - stock_cost - p.rec_costs
    profit_projected = p.revenue - stock_cost - pending - p.rec_costs
    cash = p.paid - stock_cost - p.rec_costs
    return {
        "revenue": p.revenue, "collected": p.paid, "remaining": p.remaining,
        "stock_cost": stock_cost, "recorded_costs": p.rec_costs, "pending_cost": pending,
        "profit_booked": profit_booked, "profit_projected": profit_projected, "cash_position": cash,
        "state": "final" if final else "provisional", "state_label": "قطعی" if final else "موقت",
        "profit_tone": "text-success" if profit_projected > 0 else ("text-error" if profit_projected < 0 else ""),
        "cash_tone": "text-success" if cash > 0 else ("text-error" if cash < 0 else ""),
    }


def credit_open_payments():
    qs = (Payment.objects.filter(method=Payment.Method.CREDIT, status=Payment.Status.APPROVED)
          .exclude(invoice__status=Invoice.Status.CANCELLED).select_related("invoice__project"))
    return [p for p in qs if p.credit_open_amount > 0]


def credit_open_total():
    return sum((p.credit_open_amount for p in credit_open_payments()), ZERO)


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
def settle_project_materials(*, project, final_qtys, reasons, actor):
    """
    ثبت مصرف نهایی مواد پروژه. final_qtys: {item_id: مصرف نهایی خالص}، reasons: {item_id: دلیل}.
    کالایی که مقدارش نیامده یا خالی است همان پیشنهاد سیستم را می‌گیرد.
    تغییر نسبت به پیشنهاد، دلیل اجباری دارد. کم‌شدن از انبار FIFO؛ برگشت با نوع RETURN.
    """
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند مصرف مواد را تسویه کند.")
    project = Project.objects.select_for_update().get(pk=project.pk)
    applied, total = [], ZERO
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
            consume_stock(item=item, qty=delta, user=actor, related_object=project, notes=note)
            total += delta * r["unit"]
        else:
            record_manual_stock_change(item=item, kind=CHANGE_KIND_RETURN, qty_raw=str(-delta), notes=note,
                                       user=actor, related_object=project)
            total -= (-delta) * r["unit"]
        applied.append((item.name, delta))
    if applied:
        log_event(kind=AccountingEvent.Kind.SETTLEMENT, project=project, actor=actor,
                  amount=total.quantize(Decimal("1")),
                  text="تسویه‌ی مصرف: " + "، ".join(f"{n} ({d:+f})" for n, d in applied))
    return applied


@transaction.atomic
def add_invoice_adjustment(*, invoice, title, amount_raw, kind, reason, actor):
    """ردیف دستی فاکتور بعد از قفل قیمت‌ها. kind: increase | decrease. دلیل داخلی اجباری است."""
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند فاکتور را اصلاح کند.")
    title, reason = (title or "").strip(), (reason or "").strip()
    if not title:
        raise ValueError("عنوان ردیف را بنویسید.")
    if not reason:
        raise ValueError("دلیل اصلاح را بنویسید.")
    if kind not in ("increase", "decrease"):
        raise ValueError("نوع اصلاح معتبر انتخاب کنید.")
    invoice = Invoice.objects.select_for_update().select_related("project").get(pk=invoice.pk)
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


@transaction.atomic
def settle_credit_payment(*, credit, method, amount_raw, reference_number, receipt_file, actor):
    """وصول (کامل یا بخشی) یک پرداخت اعتباری با ثبت پرداخت واقعی."""
    if not user_can_access_accounting(actor):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند وصول اعتباری را ثبت کند.")
    credit = Payment.objects.select_for_update().get(pk=credit.pk)
    if credit.method != Payment.Method.CREDIT or credit.status != Payment.Status.APPROVED:
        raise ValueError("این پرداخت، اعتباری تاییدشده نیست.")
    if method not in PROOF_METHODS:
        raise ValueError("روش وصول معتبر انتخاب کنید.")
    reference_number = (reference_number or "").strip()
    error = proof_error(method, has_file=bool(receipt_file), reference=reference_number)
    if error:
        raise ValueError(error)
    open_amount = credit.credit_open_amount
    amount = parse_amount(amount_raw) if str(amount_raw or "").strip() else open_amount
    if amount <= 0 or amount > open_amount:
        raise ValueError(f"مبلغ باید بین صفر و مانده‌ی اعتباری ({separate_digits(open_amount)} تومان) باشد.")
    invoice = Invoice.objects.select_for_update().get(pk=credit.invoice_id)
    if amount > invoice.remaining_amount:
        raise ValueError(f"مبلغ از مانده‌ی فاکتور ({separate_digits(invoice.remaining_amount)} تومان) بیشتر است.")
    kwargs = dict(invoice=invoice, method=method, amount=amount, claimed_amount=amount,
                  status=Payment.Status.APPROVED, approved_by=actor, approved_at=timezone.now(),
                  reference_number=reference_number, settles=credit, note=f"وصول اعتباری #{credit.pk}")
    if receipt_file:
        kwargs["receipt_file"] = prepare_receipt_file(receipt_file)
    payment = Payment.objects.create(**kwargs)
    log_event(kind=AccountingEvent.Kind.CREDIT, project=invoice.project, actor=actor, amount=amount,
              text=f"وصول اعتباری #{credit.pk} با {payment.get_method_display()}")
    return payment