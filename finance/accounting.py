from datetime import datetime, time
from decimal import Decimal

import jdatetime
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from inventory.models import PurchaseLine, StockLot, StockMovement
from inventory.services import low_stock_items_count
from projects.models import (
    ExtraShipment, InstallLine, PartRequest, Project, ProjectCost, ProjectServiceMaterial, ProjectStage, StageKind,
)
from .models import Invoice, Payment

ZERO = Decimal("0")
QTY_EPS = Decimal("0.0001")
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
        "stock_value": _sum(StockLot.objects.all(), LOT_VALUE),
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

    return (
        Project.objects.select_related("owner", "partner")
        .annotate(
            revenue=Coalesce(
                Case(When(invoice__status=Invoice.Status.CANCELLED, then=Value(ZERO)),
                     default=F("invoice__total_amount"), output_field=MONEY),
                Value(ZERO), output_field=MONEY),
            paid=Coalesce(F("invoice__paid_amount"), Value(ZERO), output_field=MONEY),
            stock_out=moves_sum(Q(movement_type=MT.OUT) | Q(movement_type=MT.ADJUST, direction=DIR.OUT)),
            stock_back=moves_sum(Q(movement_type=MT.ADJUST, direction=DIR.IN)),
            rec_costs=Coalesce(Subquery(cost_qs, output_field=MONEY), Value(ZERO), output_field=MONEY),
            planned_cost=Coalesce(Subquery(plan_qs, output_field=MONEY), Value(ZERO), output_field=MONEY),
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
        m.line_total = m.qty * m.unit_cost
    return moves


def project_reconciliation(project):
    """
    مغایرت مواد هر پروژه (فقط نمایش). قرارداد: «مقدار نصب‌شده» شامل قطعه‌های تحویلی از انبار هم هست.
    expected = (نصب‌شده؛ یا پیش‌فاکتور اگر نصب هنوز کامل ثبت نشده) + قطعه‌ی اضافه‌ی «مصرف شد»
    unsettled = expected − (خالص کسرشده از انبار برای این پروژه)
    status: ok | short (مصرفِ کم‌ثبت‌شده) | over (بیش از انتظار کسر شده)
    """
    ct = ContentType.objects.get_for_model(Project)
    rows = {}

    def row(item):
        return rows.setdefault(item.pk, {
            "item": item, "planned": ZERO, "installed": ZERO, "install_lines": 0, "install_pending": 0,
            "parts_issued": ZERO, "extra_consumed": ZERO, "extra_pending": ZERO, "extra_returned": ZERO,
            "out_qty": ZERO, "back_qty": ZERO, "value": ZERO,
        })

    for m in ProjectServiceMaterial.objects.filter(service_line__project=project).select_related("item"):
        row(m.item)["planned"] += m.qty
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
        if mv.movement_type == MT.OUT or (mv.movement_type == MT.ADJUST and mv.direction == DIR.OUT):
            r["out_qty"] += mv.qty
            r["value"] += val
        elif mv.movement_type == MT.ADJUST and mv.direction == DIR.IN:
            r["back_qty"] += mv.qty
            r["value"] -= val

    result = []
    for r in rows.values():
        install_done = r["install_lines"] > 0 and r["install_pending"] == 0
        if install_done:
            target = r["installed"]
        elif r["planned"] == 0 and r["install_lines"] == 0:
            target = r["parts_issued"]   # کالایی که فقط با درخواست قطعه آمده
        else:
            target = r["planned"]
        r["basis"] = "install" if install_done else "plan"
        r["net_out"] = r["out_qty"] - r["back_qty"]
        r["expected"] = target + r["extra_consumed"]
        r["unsettled"] = r["expected"] - r["net_out"]
        r["status"] = "ok" if abs(r["unsettled"]) <= QTY_EPS else ("short" if r["unsettled"] > 0 else "over")
        result.append(r)
    result.sort(key=lambda r: r["item"].name)
    return result