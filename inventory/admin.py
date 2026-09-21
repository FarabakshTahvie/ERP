from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from utils.admin_helpers import jalali_column, JalaliAdminMixin
from .models import Warehouse, Purchase, PurchaseLine, StockLot, StockMovement


@admin.register(Warehouse)
class WarehouseAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'name', 'is_default')


class PurchaseLineInline(JalaliAdminMixin, TabularInline):
    model = PurchaseLine
    extra = 1


@admin.register(Purchase)
class PurchaseAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'supplier', 'invoice_number', 'jalali_purchased_at')
    list_filter = ('purchased_at',)
    search_fields = ('supplier__name', 'invoice_number')
    readonly_fields = ('jalali_purchased_at', 'jalali_created_at')
    inlines = [PurchaseLineInline]

    jalali_purchased_at = jalali_column('purchased_at', 'تاریخ خرید')
    jalali_created_at = jalali_column('created_at', 'تاریخ ثبت')

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
class StockLotAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'item', 'warehouse', 'qty_in', 'qty_remaining', 'unit_cost', 'jalali_received_at')
    list_filter = ('warehouse', 'received_at')
    exclude = ('created_at', 'updated_at')
    readonly_fields = [f.name for f in StockLot._meta.fields if f.name not in ('received_at', 'created_at', 'updated_at')] + ['jalali_received_at', 'jalali_created_at', 'jalali_updated_at']

    jalali_received_at = jalali_column('received_at', 'تاریخ دریافت')
    jalali_created_at = jalali_column('created_at', 'تاریخ ثبت')
    jalali_updated_at = jalali_column('updated_at', 'تاریخ ویرایش')


@admin.register(StockMovement)
class StockMovementAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'item', 'lot', 'movement_type', 'qty', 'unit_cost', 'jalali_created_at')
    list_filter = ('movement_type', 'created_at')
    exclude = ('created_at', 'updated_at')
    readonly_fields = [f.name for f in StockMovement._meta.fields if f.name not in ('created_at', 'updated_at')] + ['jalali_created_at', 'jalali_updated_at']

    jalali_created_at = jalali_column('created_at', 'تاریخ ثبت')
    jalali_updated_at = jalali_column('updated_at', 'تاریخ ویرایش')
