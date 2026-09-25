from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from simple_history.admin import SimpleHistoryAdmin
from utils.admin_helpers import jalali_column, JalaliAdminMixin
from .models import Specialty, Location, Party, PartyContact


class PartyContactInline(JalaliAdminMixin, TabularInline):
    model = PartyContact
    extra = 0


@admin.register(Specialty)
class SpecialtyAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'name', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name',)


@admin.register(Location)
class LocationAdmin(JalaliAdminMixin, ModelAdmin):
    change_form_before_template = "admin/core/location/change_form_map.html"
    list_display = ('id', 'title', 'city', 'has_exact_coordinates', 'jalali_created_at')
    list_filter = ('city', 'created_at')
    search_fields = ('title', 'address_text', 'city')
    readonly_fields = ('jalali_created_at',)

    jalali_created_at = jalali_column('created_at', 'تاریخ ثبت')


@admin.register(Party)
class PartyAdmin(JalaliAdminMixin, SimpleHistoryAdmin, ModelAdmin):
    list_display = ('id', 'name', 'entity_type', 'is_partner', 'is_client', 'is_contractor', 'is_supplier', 'is_internal', 'phone_number')
    list_filter = ('entity_type', 'is_partner', 'is_client', 'is_contractor', 'is_supplier', 'is_internal')
    search_fields = ('name', 'brand_name', 'phone_number', 'national_code', 'company_registration_number', 'company_economic_code')
    raw_id_fields = ('location',)
    inlines = [PartyContactInline]
