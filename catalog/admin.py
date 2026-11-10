from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from utils.admin_helpers import jalali_column, JalaliAdminMixin
from .models import ItemCategory, Item, Service, ServiceBOM, MarginRule


@admin.register(ItemCategory)
class ItemCategoryAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'name', 'parent')
    search_fields = ('name',)


@admin.register(Item)
class ItemAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'name', 'item_type', 'unit', 'category', 'moving_average_cost', 'current_stock', 'show_to_clients', 'is_active')
    list_filter = ('item_type', 'unit', 'category', 'show_to_clients', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('moving_average_cost',)
    fields = ('name', 'item_type', 'category', 'unit', 'specs', 'reorder_point', 'responsible_user', 'show_to_clients', 'description', 'moving_average_cost', 'is_active')


class ServiceBOMInline(JalaliAdminMixin, TabularInline):
    model = ServiceBOM
    extra = 0
    autocomplete_fields = ("item",)


@admin.register(Service)
class ServiceAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'name', 'parent', 'unit', 'show_to_clients', 'is_active')
    list_filter = ('is_active', 'show_to_clients')
    search_fields = ('name', 'code')
    inlines = [ServiceBOMInline]
    exclude = ('cover', 'cover_thumb')


@admin.register(MarginRule)
class MarginRuleAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'scope', 'item', 'category', 'value_type', 'value', 'jalali_valid_from', 'jalali_valid_to', 'priority')
    list_filter = ('scope', 'value_type')

    jalali_valid_from = jalali_column('valid_from', 'معتبر از')
    jalali_valid_to = jalali_column('valid_to', 'معتبر تا')
