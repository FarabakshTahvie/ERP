from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from accounts.models import User
from catalog.models import Service, Item
from catalog.services import resolve_margin_percents
from utils.line_editor import Col, parse_rows
from .models import ProjectService, ProjectServiceMaterial, ProjectExtraLine, ProjectStage, StageKind
from .services import (
    can_edit_project, can_edit_pricing, project_prices_editable, parse_fee, advance_stage,
    NOT_SENT, EDITABLE_PROJECT_STATUSES,
)

MATERIAL_COLS = (
    Col("item_id", "کالا", "picker"),
    Col("qty", "مقدار کالا", "number", positive=True),
)
SERVICE_COLS = (
    Col("service_id", "خدمت", "picker"),
    Col("qty", "مقدار خدمت", "number", positive=True),
    Col("unit_price", "قیمت خود خدمت (تومان)", "money"),
)
EXTRA_COLS = (
    Col("title", "شرح", "text", max_len=200),
    Col("kind", "نوع", "select", choices=("extra", "discount")),
    Col("qty", "مقدار", "number", positive=True),
    Col("unit_price", "مبلغ واحد (تومان)", "money", positive=True),
)


def parse_service_rows(raw_json):
    """None = ارسال نشده."""
    return parse_rows(raw_json, SERVICE_COLS, children_key="materials", children_columns=MATERIAL_COLS)


def parse_extra_rows(raw_json):
    """None = ارسال نشده."""
    return parse_rows(raw_json, EXTRA_COLS)


def _round0(value):
    return Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def material_totals(item, qty, margin_percent):
    """(بهای میانگین، جمع فروش) — تنها فرمول رسمی قیمت کالا."""
    cost = Decimal(item.moving_average_cost or 0)
    return cost, _round0(Decimal(qty) * cost * (Decimal(100) + Decimal(margin_percent)) / Decimal(100))


def service_line_total(service_line):
    mats = sum((m.line_total for m in service_line.materials.all()), Decimal(0))
    return _round0(service_line.qty * service_line.unit_price + mats)


def proforma_stage(project):
    return project.stages.filter(kind=StageKind.PROFORMA).first()


def can_issue_proforma(user, stage):
    from .services import can_edit_pricing
    return can_edit_pricing(user, stage.project) and (
        user.is_superuser or user.role == User.Role.ADMIN or stage.assigned_to_id in (None, user.id))


def _sync_materials(line, rows, items, margins):
    existing = {m.pk: m for m in line.materials.all()}
    keep = set()
    for row in rows:
        m = existing.get(row["pk"]) if row["pk"] not in keep else None
        if m is None:
            m = ProjectServiceMaterial(service_line=line)
        item = items[row["item_id"]]
        qty = row["qty"].quantize(Decimal("0.0001"))
        if qty <= 0:
            raise ValueError("مقدار کالا خیلی کوچک است.")
        margin = Decimal(margins[item.pk]).quantize(Decimal("0.01"))
        cost, total = material_totals(item, qty, margin)
        m.item, m.qty, m.cost_snapshot, m.margin_percent, m.line_total = item, qty, cost, margin, total
        m.save()
        keep.add(m.pk)
    line.materials.exclude(pk__in=keep).delete()


def _sync_extra_rows(project, rows, actor):
    existing = {l.pk: l for l in project.extra_lines.all()}
    keep = set()
    for row in rows:
        line = existing.get(row["pk"]) if row["pk"] not in keep else None
        if line is None:
            line = ProjectExtraLine(project=project, created_by=actor)
        qty = row["qty"].quantize(Decimal("0.01"))
        if qty <= 0:
            raise ValueError("مقدار ردیف اضافه خیلی کوچک است.")
        line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
        line.save()
        keep.add(line.pk)
    project.extra_lines.exclude(pk__in=keep).delete()


def _sync_service_rows(project, rows):
    service_ids = {r["service_id"] for r in rows}
    if service_ids and Service.objects.filter(pk__in=service_ids).count() != len(service_ids):
        raise ValueError("یکی از خدمات انتخاب‌شده در سیستم پیدا نشد.")
    item_ids = {m["item_id"] for r in rows for m in r["materials"]}
    items = {i.pk: i for i in Item.objects.filter(pk__in=item_ids)}
    if len(items) != len(item_ids):
        raise ValueError("یکی از کالاهای انتخاب‌شده در سیستم پیدا نشد.")
    already_used = set(
        ProjectServiceMaterial.objects.filter(service_line__project=project).values_list("item_id", flat=True)
    )
    for iid in item_ids - already_used:
        if not items[iid].is_active:
            raise ValueError(f"کالای «{items[iid].name}» غیرفعال است.")
    margins = resolve_margin_percents(items.values())

    existing = {l.pk: l for l in project.services.all()}
    keep = set()
    for row in rows:
        line = existing.get(row["pk"]) if row["pk"] not in keep else None
        if line is None:
            line = ProjectService(project=project)
        qty = row["qty"].quantize(Decimal("0.01"))
        if qty <= 0:
            raise ValueError("مقدار خدمت خیلی کوچک است.")
        line.service_id, line.qty, line.unit_price = row["service_id"], qty, row["unit_price"]
        line.save()
        keep.add(line.pk)
        _sync_materials(line, row["materials"], items, margins)
    project.services.exclude(pk__in=keep).delete()


@transaction.atomic
def save_proforma(*, project, actor, service_rows=None, extra_rows=None, installation_fee_raw=None, shipping_fee_raw=None,
                  extra_fee_raw=None, contract_date=NOT_SENT):
    """service_rows=None یعنی دست نزن. خروجی: آیا پیش‌فاکتور بازتولید شد؟"""
    if not can_edit_pricing(actor, project):
        raise ValueError("شما اجازه‌ی ویرایش این پروژه را ندارید.")
    if project.status not in EDITABLE_PROJECT_STATUSES:
        raise ValueError("پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")
    if not project_prices_editable(project):
        raise ValueError("قیمت‌ها قفل شده‌اند (پیش‌فاکتور تایید شده یا پرداختی ثبت شده است).")

    fees = {}
    for field, raw, label in (
        ("installation_fee", installation_fee_raw, "هزینه نصب"),
        ("shipping_fee", shipping_fee_raw, "هزینه ارسال"),
        ("extra_fee", extra_fee_raw, "هزینه مازاد"),
    ):
        if raw is not None:
            fees[field] = parse_fee(raw, label=label)

    if service_rows is not None:
        _sync_service_rows(project, service_rows)
    if extra_rows is not None:
        _sync_extra_rows(project, extra_rows, actor)

    for field, value in fees.items():
        setattr(project, field, value)
    date_changed = contract_date is not NOT_SENT and project.contract_date != contract_date
    if date_changed:
        project.contract_date = contract_date
    if fees or date_changed:
        fields = ["updated_at", *fees] + (["contract_date"] if date_changed else [])
        project.save(update_fields=fields)

    invoice = getattr(project, "invoice", None)
    if invoice is not None and (service_rows is not None or extra_rows is not None or fees or date_changed):
        if date_changed:
            invoice.contract_date = project.contract_date
            invoice.save(update_fields=["contract_date"])
        from finance.services import refresh_invoice_lines
        refresh_invoice_lines(invoice)
        return True
    return False


@transaction.atomic
def issue_proforma(*, project, actor, send_sms=False):
    """صدور پیش‌فاکتور + حساب طرف‌حساب + تکمیل مرحله. خروجی: (invoice, account_conflict)"""
    from finance.services import generate_invoice_for_project, ensure_billed_party_account, notify_invoice_issued
    if not can_edit_pricing(actor, project):
        raise ValueError("شما اجازه‌ی ویرایش این پروژه را ندارید.")
    stage = proforma_stage(project)
    if stage is None or stage.status != ProjectStage.Status.IN_PROGRESS:
        raise ValueError("مرحله‌ی صدور پیش‌فاکتور فعال نیست.")
    if not can_issue_proforma(actor, stage):
        raise ValueError("فقط مسئول این مرحله می‌تواند پیش‌فاکتور صادر کند.")
    lines = list(project.services.select_related("service").prefetch_related("materials"))
    if not lines:
        raise ValueError("حداقل یک خدمت باید ثبت شود.")
    zero = [l.service.name for l in lines if service_line_total(l) <= 0]
    if zero:
        raise ValueError("جمع قیمت این خدمت‌ها صفر است: " + "، ".join(zero))

    invoice = generate_invoice_for_project(project)
    if invoice.total_amount <= 0:
        raise ValueError("جمع پیش‌فاکتور باید بیشتر از صفر باشد.")
    from finance.models import Invoice
    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=["status"])
    user, raw_password = ensure_billed_party_account(invoice)   # قبل از پیشروی؛ مرحله‌ی بعد به این حساب اطلاع می‌دهد
    advance_stage(stage, actor=actor, new_status=ProjectStage.Status.DONE, comment="پیش‌فاکتور صادر شد.")
    if send_sms and user:
        notify_invoice_issued(invoice, user, raw_password)
    return invoice, user is None
