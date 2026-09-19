from decimal import Decimal
from django.db import transaction
from django.db.models import F
from .models import StockLot, StockMovement


@transaction.atomic
def receive_stock(*, item, warehouse, qty, unit_cost, received_at, purchase_line=None):
    """ثبت لات جدید ورودی و به‌روزرسانی میانگین موزون قیمت کالا."""
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
        movement_type=StockMovement.MovementType.IN,
        qty=qty,
        unit_cost=unit_cost,
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
def consume_stock(*, item, qty, user=None, related_object=None, notes=""):
    """مصرف به روش FIFO از قدیمی‌ترین لات. اگر موجودی کافی نبود، خطا می‌دهد."""
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
            movement_type=StockMovement.MovementType.OUT,
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
        # from notifications.services import create_notification
        # from notifications.models import NotificationType
        # create_notification(
        #     notification_type=NotificationType.LOW_STOCK,
        #     user=item.responsible_user,
        #     title="هشدار موجودی کم",
        #     body=f"موجودی کالای «{item.name}» به {item.current_stock} {item.get_unit_display()} رسیده است.",
        # )
