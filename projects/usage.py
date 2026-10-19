import re
from decimal import Decimal

from django.db import transaction

from catalog.models import Item
from inventory.services import CHANGE_KIND_RETURN, consume_stock, record_manual_stock_change
from .models import FileGroup, ProjectService, ProjectStage, ServiceTick, StageKind, StageUsage
from .ops import can_edit_ops

USAGE_KINDS = (StageKind.CUTTING, StageKind.ASSEMBLY, StageKind.SHIPPING, StageKind.INSTALL)
_SHOWN = (ProjectStage.Status.IN_PROGRESS, ProjectStage.Status.DONE)
QTY_Q = Decimal("0.0001")
QTY_MAX = Decimal("9999999")
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NUMBER = re.compile(r"\d+(\.\d+)?")


def _fmt(qty):
    return format(Decimal(qty).normalize(), "f")


def parse_usage_qty(raw):
    """None = «مصرفی نبوده» (خالی یا صفر). حروف و منفی رد می‌شوند؛ اعشار با نقطه یا «٫»."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace(" ", "").replace("٫", ".")
    if not text:
        return None
    if not _NUMBER.fullmatch(text):
        raise ValueError("مقدار فقط عدد است؛ اعشار را با نقطه بنویسید (مثلاً ۴٫۵).")
    value = Decimal(text)
    if value == 0:
        return None
    if value > QTY_MAX:
        raise ValueError("مقدار بیش از حد بزرگ است.")
    value = value.quantize(QTY_Q)
    if value == 0:
        raise ValueError("مقدار خیلی کوچک است.")
    return value


def _short(usage):
    """کسری یک ردیف: مقداری که ثبت شده ولی از انبار کم نشده. خالی = ندارد."""
    if usage is None:
        return ""
    gap = usage.qty - usage.deducted
    return _fmt(gap) if gap > 0 else ""


def _deduct_up_to(*, item, want, stage, actor):
    """تا سقف موجودی از انبار کم می‌کند (وصل به پروژه). خروجی: مقدار واقعاً کم‌شده؛ موجودی کم خطا نمی‌دهد."""
    take = min(want, Decimal(item.current_stock))
    if take <= 0:
        return Decimal("0")
    consume_stock(item=item, qty=take, user=actor, related_object=stage.project,
                  notes=f"مصرف مرحله‌ی «{stage.title}»")
    return take


def _give_back(*, item, qty, stage, actor):
    record_manual_stock_change(item=item, kind=CHANGE_KIND_RETURN, qty_raw=_fmt(qty),
                               notes=f"برگشت مصرف مرحله‌ی «{stage.title}»", user=actor,
                               related_object=stage.project)


@transaction.atomic
def set_usage(*, stage, item_id, qty_raw, actor):
    """صریح و idempotent: مقدار تازه جای قبلی می‌نشیند؛ خالی/صفر ردیف را پاک می‌کند.
    همان لحظه از انبار کم می‌شود و تغییر بعدی فقط تفاوت را کم یا برمی‌گرداند. موجودی کم ثبت را رد نمی‌کند:
    هرچه هست کم می‌شود و بقیه «کسری» می‌ماند (کلید short در خروجی)."""
    stage = ProjectStage.objects.select_for_update(of=("self",)).select_related("project").get(pk=stage.pk)
    if stage.kind not in USAGE_KINDS:
        raise ValueError("برای این مرحله جدول مصرف نداریم.")
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    try:
        item = Item.objects.select_for_update(of=("self",)).get(pk=int(str(item_id).strip().translate(_FA_TO_EN)))
    except (TypeError, ValueError, Item.DoesNotExist):
        raise ValueError("کالا را از فهرست انتخاب کنید.")
    qty = parse_usage_qty(qty_raw)
    row = StageUsage.objects.filter(stage=stage, item=item).first()
    if qty is None:
        if row:
            if row.deducted > 0:
                _give_back(item=item, qty=row.deducted, stage=stage, actor=actor)
            row.delete()
        return {"qty": "", "removed": True, "short": ""}
    if row is None:
        if not item.is_active:
            raise ValueError("این کالا غیرفعال است.")
        row = StageUsage(stage=stage, item=item, deducted=Decimal("0"))
    row.qty, row.updated_by = qty, actor
    if row.deducted > qty:
        _give_back(item=item, qty=row.deducted - qty, stage=stage, actor=actor)
        row.deducted = qty
    elif row.deducted < qty:
        row.deducted += _deduct_up_to(item=item, want=qty - row.deducted, stage=stage, actor=actor)
    row.save()
    return {"qty": _fmt(qty), "removed": False, "short": _short(row)}


def stage_has_progress(stage):
    """از اولین مصرف یا تیک، مرحله به فرد دیگری واگذار نمی‌شود."""
    if stage.usages.exists():
        return True
    if stage.kind == StageKind.CUTTING:
        return FileGroup.objects.filter(project_id=stage.project_id, cut_done=True).exists()
    if stage.kind == StageKind.INSTALL:
        return stage.service_ticks.exists()
    return False


def usage_context(user, stage):
    """ردیف‌ها: کالاهای متریال پیش‌فاکتور (کادر خالی، بدون عدد پیش‌فرض) + کالاهای دیگری که همین مرحله ثبت کرده."""
    if stage.kind not in USAGE_KINDS or stage.status not in _SHOWN:
        return None
    used = {u.item_id: u for u in stage.usages.select_related("item")}
    planned = (Item.objects.filter(service_line_usages__service_line__project_id=stage.project_id)
               .distinct().order_by("name"))
    rows = []
    for item in planned:
        u = used.pop(item.pk, None)
        rows.append({"item": item, "qty": _fmt(u.qty) if u else "", "short": _short(u), "extra": False})
    for u in sorted(used.values(), key=lambda x: x.item.name):
        rows.append({"item": u.item, "qty": _fmt(u.qty), "short": _short(u), "extra": True})
    can_edit = can_edit_ops(user, stage)
    if not rows and not can_edit:
        return None
    return {"rows": rows, "can_edit": can_edit}


@transaction.atomic
def set_service_done(*, stage, service_line_id, done, actor):
    """صریح و idempotent: تیک «انجام شد» یک خدمت پیش‌فاکتور در مرحله‌ی نصب."""
    stage = ProjectStage.objects.select_for_update(of=("self",)).select_related("project").get(pk=stage.pk)
    if stage.kind != StageKind.INSTALL:
        raise ValueError("این عملیات فقط برای مرحله‌ی نصب است.")
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    try:
        line = ProjectService.objects.filter(pk=int(str(service_line_id).strip().translate(_FA_TO_EN)),
                                             project_id=stage.project_id).first()
    except (TypeError, ValueError):
        line = None
    if line is None:
        raise ValueError("خدمت نامعتبر است.")
    if done:
        ServiceTick.objects.get_or_create(stage=stage, service_line=line, defaults={"done_by": actor})
    else:
        ServiceTick.objects.filter(stage=stage, service_line=line).delete()
    return {"done": ServiceTick.objects.filter(stage=stage).count(),
            "total": ProjectService.objects.filter(project_id=stage.project_id).count()}


def install_context(user, stage):
    if stage.kind != StageKind.INSTALL or stage.status not in _SHOWN:
        return None
    ticked = set(ServiceTick.objects.filter(stage=stage).values_list("service_line_id", flat=True))
    rows = [{"line": ps, "done": ps.pk in ticked}
            for ps in ProjectService.objects.filter(project_id=stage.project_id).select_related("service").order_by("pk")]
    return {"rows": rows, "total": len(rows), "done": sum(1 for r in rows if r["done"]),
            "can_edit": can_edit_ops(user, stage)}


def project_usage_by_stage(project):
    """[{stage, rows: [{item, qty, unit, extra, by}]}] فقط مرحله‌هایی که مصرف ثبت کرده‌اند، به ترتیب مرحله."""
    planned = set(Item.objects.filter(service_line_usages__service_line__project_id=project.pk)
                  .values_list("pk", flat=True))
    qs = (StageUsage.objects.filter(stage__project=project)
          .select_related("item", "stage", "stage__assigned_to", "updated_by")
          .order_by("stage__order", "item__name"))
    out, current = [], None
    for u in qs:
        if current is None or current["stage"].pk != u.stage_id:
            current = {"stage": u.stage, "rows": []}
            out.append(current)
        current["rows"].append({"item": u.item, "qty": u.qty, "unit": u.item.get_unit_display(),
                                "extra": u.item_id not in planned, "by": u.updated_by,
                                "short": (u.qty - u.deducted) if u.qty > u.deducted else None})
    return out


