import re
from decimal import Decimal

from django.db import transaction

from catalog.models import Item
from .models import FileGroup, ProjectStage, StageKind, StageUsage
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


@transaction.atomic
def set_usage(*, stage, item_id, qty_raw, actor):
    """صریح و idempotent: مقدار تازه جای قبلی می‌نشیند؛ خالی/صفر ردیف را پاک می‌کند."""
    stage = ProjectStage.objects.select_for_update(of=("self",)).select_related("project").get(pk=stage.pk)
    if stage.kind not in USAGE_KINDS:
        raise ValueError("برای این مرحله جدول مصرف نداریم.")
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    try:
        item = Item.objects.get(pk=int(str(item_id).strip().translate(_FA_TO_EN)))
    except (TypeError, ValueError, Item.DoesNotExist):
        raise ValueError("کالا را از فهرست انتخاب کنید.")
    qty = parse_usage_qty(qty_raw)
    existing = StageUsage.objects.filter(stage=stage, item=item).first()
    if qty is None:
        if existing:
            existing.delete()
        return {"qty": "", "removed": True}
    if existing is None and not item.is_active:
        raise ValueError("این کالا غیرفعال است.")
    if existing:
        existing.qty, existing.updated_by = qty, actor
        existing.save(update_fields=["qty", "updated_by", "updated_at"])
    else:
        StageUsage.objects.create(stage=stage, item=item, qty=qty, updated_by=actor)
    return {"qty": _fmt(qty), "removed": False}


def stage_has_progress(stage):
    """از اولین مصرف یا تیک، مرحله به فرد دیگری واگذار نمی‌شود."""
    if stage.usages.exists():
        return True
    if stage.kind == StageKind.CUTTING:
        return FileGroup.objects.filter(project_id=stage.project_id, cut_done=True).exists()
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
        rows.append({"item": item, "qty": _fmt(u.qty) if u else "", "extra": False})
    for u in sorted(used.values(), key=lambda x: x.item.name):
        rows.append({"item": u.item, "qty": _fmt(u.qty), "extra": True})
    can_edit = can_edit_ops(user, stage)
    if not rows and not can_edit:
        return None
    return {"rows": rows, "can_edit": can_edit}
