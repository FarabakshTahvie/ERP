import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Case, IntegerField, When, Prefetch
from django.utils import timezone
from accounts.models import User
from catalog.models import Item
from catalog.services import resolve_margin_percents
from inventory.services import consume_stock, user_can_manage_inventory, parse_decimal_input
from utils.image_utils import optimize_receipt_image
from .models import (
    ExtraShipment, InstallLine, PartRequest, Project, ProjectCost, ProjectFile, ProjectStage, ShipmentCheck, StageEvent, StageKind,
)
from .proforma import material_totals
from .services import parse_fee, user_is_accountant
from .stage_ops import cut_files, _is_manager

REASON_MAX = 1000
_ACTIVE = (ProjectStage.Status.IN_PROGRESS, ProjectStage.Status.DONE)


def prepare_part_photo(f):
    ext = (f.name or "").lower().rsplit(".", 1)[-1]
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        raise ValueError("فرمت عکس مجاز نیست؛ JPG، PNG یا WEBP بفرستید.")
    if f.size > 10 * 1024 * 1024:
        raise ValueError("حجم عکس بیشتر از ۱۰ مگابایت است.")
    prepared, changed = optimize_receipt_image(f)
    prepared.name = f"{uuid.uuid4().hex[:16]}.{'webp' if changed else ext}"
    return prepared


def _round0(v):
    return Decimal(v).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _reason(raw, *, required, label="دلیل"):
    text = (raw or "").strip()
    if required and not text:
        raise ValueError(f"نوشتن «{label}» اجباری است.")
    if len(text) > REASON_MAX:
        raise ValueError(f"«{label}» بیش از حد طولانی است.")
    return text


def is_creator_or_manager(user, project):
    return user.is_authenticated and (_is_manager(user) or project.created_by_id == user.id)


from core.capabilities import can

def can_view_final_review(user, project):
    return can(user, "final_review.view")


def review_open(project):
    st = project.stages.filter(kind=StageKind.FINAL_REVIEW).first()
    return st is None or st.status != ProjectStage.Status.DONE


def can_edit_ops(user, stage):
    """نصاب/راننده فقط تا وقتی مرحله‌ی خودشان در حال انجام است؛ ثبت‌کننده‌ی پروژه و مدیر تا قبل از تایید بازبینی نهایی."""
    project = stage.project
    if not user.is_authenticated or project.status == Project.Status.CANCELLED:
        return False
    if is_creator_or_manager(user, project):
        return stage.status in _ACTIVE and review_open(project)
    return stage.assigned_to_id == user.id and stage.status == ProjectStage.Status.IN_PROGRESS


def _log(stage, actor, text):
    StageEvent.objects.create(stage=stage, actor=actor, from_status=stage.status, to_status=stage.status, comment=text)


def _need(stage, kind):
    if stage.kind != kind:
        raise ValueError("این عملیات برای این مرحله معتبر نیست.")


# ---------------- ارسال ----------------
@transaction.atomic
def set_shipment_check(*, stage, file, status, reason, actor):
    _need(stage, StageKind.SHIPPING)
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    if status not in ShipmentCheck.Status.values:
        raise ValueError("وضعیت نامعتبر است.")
    if file.stage.project_id != stage.project_id or file.stage.kind != StageKind.GCODE or not file.cut_count:
        raise ValueError("فایل نامعتبر است.")
    not_sent = status == ShipmentCheck.Status.NOT_SENT
    text = _reason(reason, required=not_sent, label="دلیل ارسال‌نشدن") if not_sent else ""
    ShipmentCheck.objects.update_or_create(
        stage=stage, file=file, defaults={"status": status, "reason": text, "checked_by": actor})


def shipment_rows(stage):
    checks = {c.file_id: c for c in stage.shipment_checks.all()}
    return [{"file": f, "status": checks[f.pk].status if f.pk in checks else "", "reason": checks[f.pk].reason if f.pk in checks else ""}
            for f in cut_files(stage.project)]


def shipping_problem(stage):
    total = cut_files(stage.project).count()
    done = stage.shipment_checks.filter(file__in=cut_files(stage.project)).count()
    if done < total:
        return f"برای {total - done} فایل هنوز «ارسال شد» یا «ارسال نشد» ثبت نشده است."
    return None


def _item_price(item, qty):
    margin = Decimal(resolve_margin_percents([item])[item.pk]).quantize(Decimal("0.01"))
    cost, total = material_totals(item, qty, margin)
    return cost, margin, total


def _qty(raw):
    qty = parse_decimal_input(raw, label="مقدار").quantize(Decimal("0.0001"))
    if qty <= 0:
        raise ValueError("مقدار خیلی کوچک است.")
    return qty


def _active_item(item_id):
    try:
        return Item.objects.get(pk=int(item_id), is_active=True)
    except (TypeError, ValueError, Item.DoesNotExist):
        raise ValueError("کالا را از فهرست انتخاب کنید.")


@transaction.atomic
def add_extra_shipment(*, stage, item_id, qty_raw, note, actor):
    _need(stage, StageKind.SHIPPING)
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    item, qty = _active_item(item_id), _qty(qty_raw)
    text = _reason(note, required=True, label="توضیح")
    cost, margin, total = _item_price(item, qty)
    return ExtraShipment.objects.create(
        project=stage.project, stage=stage, item=item, qty=qty, cost_snapshot=cost,
        margin_percent=margin, sale_total=total, note=text, created_by=actor)


@transaction.atomic
def delete_extra_shipment(*, extra, actor):
    if not can_edit_ops(actor, extra.stage):
        raise ValueError("شما اجازه‌ی حذف ندارید.")
    _log(extra.stage, actor, f"کالای اضافه‌ی ارسال حذف شد: {extra.item.name} × {extra.qty.normalize():f}")
    extra.delete()


# ---------------- نصب ----------------
def ensure_install_lines(stage):
    """idempotent؛ مقدار و قیمت را از پیش‌فاکتور (که بعد از تایید قفل است) اسنپ‌شات می‌کند."""
    if stage.kind != StageKind.INSTALL:
        return
    with transaction.atomic():
        ProjectStage.objects.select_for_update().get(pk=stage.pk)
        have_s = set(stage.install_lines.filter(kind=InstallLine.Kind.SERVICE).values_list("service_line_id", flat=True))
        have_m = set(stage.install_lines.filter(kind=InstallLine.Kind.MATERIAL).values_list("material_line_id", flat=True))
        for ps in stage.project.services.select_related("service").prefetch_related("materials__item"):
            if ps.pk not in have_s:
                InstallLine.objects.create(
                    stage=stage, kind=InstallLine.Kind.SERVICE, service_line=ps, title=ps.service.name,
                    unit=ps.service.get_unit_display() if ps.service.unit else "", planned_qty=ps.qty)
            for m in ps.materials.all():
                if m.pk not in have_m:
                    InstallLine.objects.create(
                        stage=stage, kind=InstallLine.Kind.MATERIAL, service_line=ps, material_line=m, item=m.item,
                        title=m.item.name, unit=m.item.get_unit_display(), planned_qty=m.qty,
                        unit_cost=m.cost_snapshot, margin_percent=m.margin_percent)


@transaction.atomic
def set_install_line(*, line, status, actual_qty_raw, reason, actor):
    line = InstallLine.objects.select_for_update(of=("self",)).select_related("stage__project").get(pk=line.pk)
    if not can_edit_ops(actor, line.stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    if status not in (InstallLine.Status.OK, InstallLine.Status.NOT_OK):
        raise ValueError("وضعیت نامعتبر است.")
    is_material = line.kind == InstallLine.Kind.MATERIAL
    if status == InstallLine.Status.NOT_OK:
        line.reason = _reason(reason, required=True, label="دلیل نصب‌نشدن")
        line.actual_qty, line.delta_qty, line.delta_sale = None, None, Decimal(0)
    else:
        line.reason = ""
        if is_material:
            raw = actual_qty_raw if str(actual_qty_raw or "").strip() else line.planned_qty
            qty = _qty(raw)
            line.actual_qty = qty
            line.delta_qty = qty - line.planned_qty
            value = _round0(abs(line.delta_qty) * line.unit_cost * (Decimal(100) + line.margin_percent) / Decimal(100))
            line.delta_sale = value if line.delta_qty >= 0 else -value
        else:
            line.actual_qty = line.delta_qty = None
            line.delta_sale = Decimal(0)
    line.status, line.updated_by = status, actor
    line.save()
    return line


def install_groups(stage):
    ensure_install_lines(stage)
    lines = list(stage.install_lines.select_related("item"))
    groups = []
    for s in (l for l in lines if l.kind == InstallLine.Kind.SERVICE):
        groups.append({"service": s, "materials": [m for m in lines if m.kind == InstallLine.Kind.MATERIAL and m.service_line_id == s.service_line_id]})
    return groups


def install_problem(stage):
    ensure_install_lines(stage)
    pending = stage.install_lines.filter(status=InstallLine.Status.PENDING).count()
    if pending:
        return f"برای {pending} مورد هنوز «نصب شد» یا «نصب نشد» ثبت نشده است."
    # درخواست قطعه‌ی بدون‌پاسخ دیگر مانع تکمیل مرحله‌ی نصب نیست؛ نصاب می‌تواند کارش را تمام کند
    # و درخواست سرجای خودش برای انباردار باقی می‌ماند. فقط بازبینی نهایی همچنان تا پاسخ‌دادن
    # به آن بسته می‌ماند (در stage_completion_problem، بدون تغییر).
    return None


# ---------------- درخواست قطعه ----------------
def pending_part_requests(project):
    return PartRequest.objects.filter(project=project, status=PartRequest.Status.REQUESTED)


def notify_part_request(req):
    from inventory.services import warehouse_keepers
    from notifications.models import NotificationType
    from notifications.services import notify_users
    notify_users(warehouse_keepers(), notification_type=NotificationType.PART_REQUEST,
                 title="درخواست قطعه‌ی جدید",
                 body=f"«{req.item.name}» × {format(req.qty.normalize(), 'f')} برای پروژه «{req.project.name}»",
                 real_target_url=f"/staff/part-requests/{req.id}/")


@transaction.atomic
def create_part_request(*, stage, item_id, qty_raw, note, actor):
    _need(stage, StageKind.INSTALL)
    if not can_edit_ops(actor, stage):
        raise ValueError("شما اجازه‌ی ثبت در این مرحله را ندارید.")
    item, qty = _active_item(item_id), _qty(qty_raw)
    text = _reason(note, required=True, label="دلیل درخواست")
    req = PartRequest.objects.create(project=stage.project, stage=stage, item=item, qty=qty, note=text, requested_by=actor)
    notify_part_request(req)
    return req


@transaction.atomic
def issue_part_request(*, req, actor, shipping_cost_raw="", photo=None):
    if not user_can_manage_inventory(actor):
        raise ValueError("فقط انباردار می‌تواند قطعه تحویل دهد.")
    amount = parse_fee(shipping_cost_raw, label="هزینه ارسال")
    photo_file = prepare_part_photo(photo) if photo else None

    req = PartRequest.objects.select_for_update(of=("self",)).select_related("item", "project").get(pk=req.pk)
    if req.status != PartRequest.Status.REQUESTED:
        raise ValueError("این درخواست قبلاً بررسی شده است.")
    breakdown = consume_stock(item=req.item, qty=req.qty, user=actor, related_object=req.project,
                              notes=f"درخواست قطعه #{req.pk}")
    cost = _round0(sum((take * unit_cost for _lot, take, unit_cost in breakdown), Decimal(0)))
    margin = Decimal(resolve_margin_percents([req.item])[req.item.pk]).quantize(Decimal("0.01"))
    req.cost_total, req.margin_percent = cost, margin
    req.sale_total = _round0(cost * (Decimal(100) + margin) / Decimal(100))
    if photo_file:
        req.photo = photo_file
    req.status, req.decided_by, req.decided_at = PartRequest.Status.ISSUED, actor, timezone.now()
    req.save()

    if amount > 0:
        ProjectCost.objects.create(
            project=req.project,
            kind=ProjectCost.Kind.PART_SHIPPING,
            title=f"ارسال «{req.item.name}»",
            amount=amount,
            created_by=actor,
            part_request=req,
        )
    return req


@transaction.atomic
def reject_part_request(*, req, actor, reason):
    if not user_can_manage_inventory(actor):
        raise ValueError("فقط انباردار می‌تواند درخواست را رد کند.")
    text = _reason(reason, required=True, label="دلیل رد")
    req = PartRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != PartRequest.Status.REQUESTED:
        raise ValueError("این درخواست قبلاً بررسی شده است.")
    req.status, req.decided_by, req.decided_at, req.decision_note = PartRequest.Status.REJECTED, actor, timezone.now(), text
    req.save()


@transaction.atomic
def cancel_part_request(*, req, actor):
    req = PartRequest.objects.select_for_update(of=("self",)).select_related("stage__project").get(pk=req.pk)
    if req.status != PartRequest.Status.REQUESTED:
        raise ValueError("این درخواست قبلاً بررسی شده و قابل لغو نیست.")
    if not (req.requested_by_id == actor.id or is_creator_or_manager(actor, req.project)):
        raise ValueError("شما اجازه‌ی لغو ندارید.")
    req.status, req.decided_by, req.decided_at = PartRequest.Status.CANCELLED, actor, timezone.now()
    req.save()


# ---------------- هزینه‌ها ----------------
def can_manage_costs(user, project):
    return can(user, "costs.manage")


@transaction.atomic
def add_project_cost(*, project, kind, title, amount_raw, actor):
    if not can_manage_costs(actor, project):
        raise ValueError("فقط حسابدار می‌تواند هزینه ثبت کند.")
    if kind not in ProjectCost.Kind.values:
        raise ValueError("نوع هزینه معتبر نیست.")
    amount = parse_fee(amount_raw, label="مبلغ")
    if amount <= 0:
        raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد.")
    return ProjectCost.objects.create(project=project, kind=kind, title=_reason(title, required=True, label="شرح"),
                                      amount=amount, created_by=actor)


@transaction.atomic
def delete_project_cost(*, cost, actor):
    if not can_manage_costs(actor, cost.project):
        raise ValueError("شما اجازه‌ی حذف ندارید.")
    stage = cost.project.stages.order_by("order").first()
    if stage:
        _log(stage, actor, f"هزینه حذف شد: {cost.title} ({cost.amount})")
    cost.delete()


# ---------------- نمایش ----------------
def ops_context(user, stage):
    """کانتکست کشوی عملیات هر مرحله؛ مبلغ‌ها فقط برای مدیر و حسابدار."""
    if stage.kind not in (StageKind.SHIPPING, StageKind.INSTALL):
        return None
    project = stage.project
    money = can(user, "money.view")
    ctx = {"can_edit": can_edit_ops(user, stage), "show_money": money}
    if stage.kind == StageKind.SHIPPING:
        ctx["rows"] = shipment_rows(stage)
        ctx["extras"] = list(stage.extra_shipments.select_related("item"))
    elif stage.status in _ACTIVE:
        ctx["groups"] = install_groups(stage)
        ctx["requests"] = list(stage.part_requests.select_related("item"))
    return ctx


def final_review_data(project):
    stages = list(project.stages.prefetch_related("events__actor", Prefetch("files", queryset=ProjectFile.objects.select_related("uploaded_by"))).order_by("order"))
    lines = list(InstallLine.objects.filter(stage__project=project).select_related("item"))
    extras = list(project.extra_shipments.select_related("item"))
    parts = list(project.part_requests.select_related("item", "requested_by"))
    costs = list(project.recorded_costs.all())
    shortage = [l for l in lines if l.delta_qty and l.delta_qty > 0]
    surplus = [l for l in lines if l.delta_qty and l.delta_qty < 0]
    t = {
        "costs_total": sum((c.amount for c in costs), Decimal(0)),
    }
    return {
        "stages": stages, "totals": t, "extras": extras, "parts": parts, "costs": costs,
        "not_sent": list(ShipmentCheck.objects.filter(stage__project=project, status=ShipmentCheck.Status.NOT_SENT).select_related("file")),
        "not_installed": [l for l in lines if l.status == InstallLine.Status.NOT_OK],
        "shortage": shortage,
        "surplus": surplus,
        "pending_parts": pending_part_requests(project).count(),
    }
