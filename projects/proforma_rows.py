import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from catalog.models import Item, Service
from utils.jalali import jalali_str, to_fa_digits
from utils.jalali_forms import JalaliDateField
from utils.line_editor import parse_rows
from utils.utils import separate_digits
from .models import Project, ProjectExtraLine, ProjectService
from .proforma import (
    EXTRA_COLS, MATERIAL_COLS, SERVICE_COLS, _round0, _sync_materials, check_material_items, service_line_total,
)
from .services import EDITABLE_PROJECT_STATUSES, can_edit_pricing, parse_fee, project_prices_editable

FEES = {"installation_fee": "هزینه نصب", "shipping_fee": "هزینه ارسال", "extra_fee": "هزینه‌های مازاد"}
CONTRACT_DATE = "contract_date"
KIND_LABELS = {"extra": "هزینه‌ی اضافه", "discount": "تخفیف"}
NOT_FOUND = "این ردیف پیدا نشد؛ صفحه را تازه کنید."


def money_text(value):
    return to_fa_digits(separate_digits(value))


def _q(value):
    return to_fa_digits(format(Decimal(value).normalize(), "f"))


def _change(label, old, new):
    return {"label": label, "old": old, "new": new}


def _int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# ---------- ورودی ----------
def _only_one(rows):
    if rows is None or len(rows) != 1:
        raise ValueError("اطلاعات ردیف نامعتبر است؛ صفحه را دوباره باز کنید.")
    return rows[0]


def parse_service_row(raw_json):
    return _only_one(parse_rows(raw_json, SERVICE_COLS, children_key="materials", children_columns=MATERIAL_COLS))


def parse_extra_row(raw_json):
    return _only_one(parse_rows(raw_json, EXTRA_COLS))


def _parse_date(raw):
    text = (raw or "").strip()
    try:
        return JalaliDateField().clean(text) if text else None
    except ValidationError as e:
        raise ValueError(" ".join(e.messages))


# ---------- خلاصه‌ی عددی (تنها منبع عدد صفحه) ----------
def service_row_initial(line):
    q = lambda v: format(Decimal(v).normalize(), "f")
    saved = sorted(line.materials.all(), key=lambda m: m.pk)
    have = {m.item_id for m in saved}
    mats = [{"pk": m.pk, "item_id": m.item_id, "on": True} for m in saved]
    mats += [{"item_id": b.item_id, "on": False} for b in line.service.bom_lines.all()
             if b.item_id not in have and b.item.is_active]
    return {"pk": line.pk, "service_id": line.service_id, "qty": q(line.qty),
            "unit_price": str(int(line.unit_price)), "materials": mats}


def extra_row_initial(x):
    return {"pk": x.pk, "title": x.title, "kind": x.kind, "qty": format(Decimal(x.qty).normalize(), "f"),
            "unit_price": str(int(x.unit_price))}


def _signed(x):
    t = _round0(Decimal(x.qty) * Decimal(x.unit_price))
    return -t if x.kind == ProjectExtraLine.Kind.DISCOUNT else t


def proforma_summary(project):
    total, services, extras = Decimal(0), [], []
    qs = project.services.select_related("service").prefetch_related("materials__item", "service__bom_lines__item").order_by("pk")
    for line in qs:
        t = service_line_total(line)
        total += t
        services.append({"line": line, "total": t, "materials": sorted(line.materials.all(), key=lambda m: m.pk),
                         "json": json.dumps(service_row_initial(line), ensure_ascii=False)})
    for x in project.extra_lines.all():
        t = _signed(x)
        total += t
        extras.append({"line": x, "total": t, "json": json.dumps(extra_row_initial(x), ensure_ascii=False)})
    fees = []
    for field, label in FEES.items():
        value = getattr(project, field)
        total += value
        fees.append({"field": field, "label": label, "value": value, "raw": str(int(value)) if value else ""})
    participants = project.participants.aggregate(t=Sum("agreed_cost"))["t"] or 0
    total += participants
    from finance.models import InvoiceLine
    manual = list(InvoiceLine.objects.filter(invoice__project=project, is_manual=True).order_by("pk"))
    total += sum((l.total for l in manual), Decimal(0))
    return {"services": services, "extras": extras, "fees": fees, "participants_cost": participants,
            "manual_lines": manual,
            "contract_date": project.contract_date,
            "contract_raw": jalali_str(project.contract_date, fmt="%Y/%m/%d") if project.contract_date else "",
            "grand_total": total}


# ---------- نوشتن ----------
def _locked(project):
    return Project.objects.select_for_update(of=("self",)).get(pk=project.pk)


def _guard(project, actor):
    if not can_edit_pricing(actor, project):
        raise ValueError("شما اجازه‌ی ویرایش این پروژه را ندارید.")
    if project.status not in EDITABLE_PROJECT_STATUSES:
        raise ValueError("پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")
    from finance.models import Invoice
    invoice = getattr(project, "invoice", None)
    if invoice is not None and invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("فاکتور لغو شده است؛ ردیف‌ها قابل ویرایش نیست.")
    if not project_prices_editable(project):
        raise ValueError("قیمت‌ها قفل شده‌اند (پیش‌فاکتور تایید شده یا پرداختی ثبت شده است).")


def _refresh_invoice(project):
    from finance.models import Invoice
    from finance.services import refresh_invoice_lines
    invoice = Invoice.objects.filter(project=project).first()
    if invoice is None:
        return None
    if invoice.contract_date != project.contract_date:
        invoice.contract_date = project.contract_date
        invoice.save(update_fields=["contract_date"])
    refresh_invoice_lines(invoice)
    # TODO(پیامک invoice_updated): همان نقطه‌ی save_proforma؛ فاکتور بازتولید شد.
    return invoice


def _line_or_none(qs, pk, required=False):
    if not pk:
        if required:
            raise ValueError(NOT_FOUND)
        return None
    obj = qs.filter(pk=_int(pk)).first()
    if obj is None:
        raise ValueError(NOT_FOUND)
    return obj


@transaction.atomic
def save_service_line(*, project, actor, row):
    project = _locked(project)
    _guard(project, actor)
    if not Service.objects.filter(pk=row["service_id"]).exists():
        raise ValueError("خدمت انتخاب‌شده در سیستم پیدا نشد.")
    qty = row["qty"].quantize(Decimal("0.01"))
    if qty <= 0:
        raise ValueError("مقدار خدمت خیلی کوچک است.")
    line = _line_or_none(project.services.all(), row["pk"]) or ProjectService(project=project)
    check_material_items(project, row["materials"])
    line.service_id, line.qty, line.unit_price = row["service_id"], qty, row["unit_price"]
    line.save()
    _sync_materials(line, row["materials"])   # فقط همین ردیف
    _refresh_invoice(project)
    return line


@transaction.atomic
def save_extra_line(*, project, actor, row):
    project = _locked(project)
    _guard(project, actor)
    qty = row["qty"].quantize(Decimal("0.01"))
    if qty <= 0:
        raise ValueError("مقدار ردیف خیلی کوچک است.")
    line = _line_or_none(project.extra_lines.all(), row["pk"]) or ProjectExtraLine(project=project, created_by=actor)
    line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
    line.save()
    _refresh_invoice(project)
    return line


@transaction.atomic
def delete_line(*, project, actor, kind, pk):
    project = _locked(project)
    _guard(project, actor)
    qs = {"service": project.services.all(), "extra": project.extra_lines.all()}.get(kind)
    if qs is None:
        raise ValueError("نوع ردیف نامعتبر است.")
    line = _line_or_none(qs, pk, required=True)
    if kind == "service" and project.services.count() == 1:
        from finance.models import Invoice
        if Invoice.objects.filter(project=project).exists():
            raise ValueError("پیش‌فاکتور صادرشده باید حداقل یک خدمت داشته باشد.")
    line.delete()
    _refresh_invoice(project)


@transaction.atomic
def set_project_field(*, project, actor, field, raw):
    project = _locked(project)
    _guard(project, actor)
    if field == CONTRACT_DATE:
        value = _parse_date(raw)
        if project.contract_date == value:
            return project
        project.contract_date = value
    elif field in FEES:
        value = parse_fee(raw, label=FEES[field])
        if getattr(project, field) == value:
            return project
        setattr(project, field, value)
    else:
        raise ValueError("فیلد نامعتبر است.")
    project.save(update_fields=["updated_at", field])
    _refresh_invoice(project)
    return project


# ---------- پیش‌نمایش «چه به چه» (چیزی ذخیره نمی‌شود) ----------
def _old_view(line):
    return {"name": line.service.name, "qty": line.qty, "unit_price": line.unit_price,
            "items": {m.item_id: m.item.name for m in sorted(line.materials.all(), key=lambda m: m.pk)},
            "total": service_line_total(line)}


def _new_view(row):
    service = Service.objects.filter(pk=row["service_id"]).first()
    if service is None:
        raise ValueError("خدمت انتخاب‌شده در سیستم پیدا نشد.")
    ids = {m["item_id"] for m in row["materials"]}
    names = {i.pk: i.name for i in Item.objects.filter(pk__in=ids)}
    if len(names) != len(ids):
        raise ValueError("یکی از کالاهای انتخاب‌شده در سیستم پیدا نشد.")
    qty = row["qty"].quantize(Decimal("0.01"))
    return {"name": service.name, "qty": qty, "unit_price": row["unit_price"],
            "items": {m["item_id"]: names[m["item_id"]] for m in row["materials"] if m.get("on")},
            "total": _round0(qty * row["unit_price"])}


def _diff_service(old, new):
    out = []
    if old["name"] != new["name"]:
        out.append(_change("خدمت", old["name"], new["name"]))
    if old["qty"] != new["qty"]:
        out.append(_change("مقدار خدمت", _q(old["qty"]), _q(new["qty"])))
    if old["unit_price"] != new["unit_price"]:
        out.append(_change("قیمت خود خدمت (تومان)", money_text(old["unit_price"]), money_text(new["unit_price"])))
    for iid, name in new["items"].items():
        if iid not in old["items"]:
            out.append(_change("کالای اضافه‌شده به فرم مصرف", "—", name))
    for iid, name in old["items"].items():
        if iid not in new["items"]:
            out.append(_change("کالای برداشته‌شده از فرم مصرف", name, "—"))
    if old["total"] != new["total"]:
        out.append(_change("جمع این ردیف (تومان)", money_text(old["total"]), money_text(new["total"])))
    return out


def _extra_view(kind, title, qty, unit_price):
    t = _round0(Decimal(qty) * Decimal(unit_price))
    return {"kind": kind, "title": title, "qty": Decimal(qty), "unit_price": Decimal(unit_price),
            "total": -t if kind == ProjectExtraLine.Kind.DISCOUNT else t}


def _diff_extra(old, new):
    out = []
    if old["title"] != new["title"]:
        out.append(_change("شرح", old["title"], new["title"]))
    if old["kind"] != new["kind"]:
        out.append(_change("نوع", KIND_LABELS[old["kind"]], KIND_LABELS[new["kind"]]))
    if old["qty"] != new["qty"]:
        out.append(_change("مقدار", _q(old["qty"]), _q(new["qty"])))
    if old["unit_price"] != new["unit_price"]:
        out.append(_change("مبلغ واحد (تومان)", money_text(old["unit_price"]), money_text(new["unit_price"])))
    if old["total"] != new["total"]:
        out.append(_change("اثر روی جمع (تومان)", money_text(old["total"]), money_text(new["total"])))
    return out


def _fee_change(project, field, raw):
    if field == CONTRACT_DATE:
        new = _parse_date(raw)
        show = lambda d: jalali_str(d, fmt="%Y/%m/%d") if d else "—"
        same = project.contract_date == new
        return ([] if same else [_change("تاریخ قرارداد", show(project.contract_date), show(new))]), Decimal(0)
    if field not in FEES:
        raise ValueError("فیلد نامعتبر است.")
    new, old = parse_fee(raw, label=FEES[field]), getattr(project, field)
    show = lambda v: money_text(v) if v else "—"
    return ([] if old == new else [_change(f"{FEES[field]} (تومان)", show(old), show(new))]), new - old


def _result(before, delta, changes, is_new=False):
    return {"is_new": is_new, "same": not changes, "changes": changes,
            "grand_before": money_text(before), "grand_after": money_text(before + delta)}


def preview_change(*, project, actor, kind, row=None, field=None, raw=None):
    _guard(project, actor)
    before = proforma_summary(project)["grand_total"]
    if kind == "service":
        base = project.services.select_related("service").prefetch_related("materials__item")
        line = _line_or_none(base, row["pk"])
        new = _new_view(row)
        if line is None:
            return _result(before, new["total"], [_change(f"ردیف تازه: {new['name']}", "—",
                                                          f"{money_text(new['total'])} تومان")], is_new=True)
        old = _old_view(line)
        return _result(before, new["total"] - old["total"], _diff_service(old, new))
    if kind == "extra":
        line = _line_or_none(project.extra_lines.all(), row["pk"])
        qty = row["qty"].quantize(Decimal("0.01"))
        new = _extra_view(row["kind"], row["title"], qty, row["unit_price"])
        if line is None:
            return _result(before, new["total"], [_change(f"ردیف تازه: {new['title']}", "—",
                                                          f"{money_text(new['total'])} تومان")], is_new=True)
        old = _extra_view(line.kind, line.title, line.qty, line.unit_price)
        return _result(before, new["total"] - old["total"], _diff_extra(old, new))
    if kind == "fee":
        changes, delta = _fee_change(project, field, raw)
        return _result(before, delta, changes)
    raise ValueError("نوع ردیف نامعتبر است.")


def preview_delete(*, project, actor, kind, pk):
    _guard(project, actor)
    before = proforma_summary(project)["grand_total"]
    if kind == "service":
        line = _line_or_none(project.services.select_related("service").prefetch_related("materials"), pk, True)
        name, total = line.service.name, service_line_total(line)
    elif kind == "extra":
        line = _line_or_none(project.extra_lines.all(), pk, True)
        name, total = line.title, _signed(line)
    else:
        raise ValueError("نوع ردیف نامعتبر است.")
    return _result(before, -total, [_change(f"حذف ردیف: {name}", f"{money_text(total)} تومان", "—")])
