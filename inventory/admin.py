from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Warehouse, Purchase, PurchaseLine, StockLot, StockMovement


@admin.register(Warehouse)
class WarehouseAdmin(ModelAdmin):
    list_display = ('id', 'name', 'is_default')


class PurchaseLineInline(TabularInline):
    model = PurchaseLine
    extra = 1


@admin.register(Purchase)
class PurchaseAdmin(ModelAdmin):
    list_display = ('id', 'supplier', 'invoice_number', 'purchased_at')
    list_filter = ('purchased_at',)
    search_fields = ('supplier__name', 'invoice_number')
    inlines = [PurchaseLineInline]

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        from .services import receive_stock
        for line in instances:
            line.save()
            receive_stock(
                item=line.item,
                warehouse=line.warehouse,
                qty=line.qty,
                unit_cost=line.unit_cost,
                received_at=form.instance.purchased_at,
                purchase_line=line,
            )
        formset.save_m2m()


@admin.register(StockLot)
class StockLotAdmin(ModelAdmin):
    list_display = ('id', 'item', 'warehouse', 'qty_in', 'qty_remaining', 'unit_cost', 'received_at')
    list_filter = ('warehouse', 'received_at')
    readonly_fields = [f.name for f in StockLot._meta.fields]


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):
    list_display = ('id', 'item', 'lot', 'movement_type', 'qty', 'unit_cost', 'created_at')
    list_filter = ('movement_type', 'created_at')
    readonly_fields = [f.name for f in StockMovement._meta.fields]
