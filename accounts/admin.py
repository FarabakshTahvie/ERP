from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import ChoicesDropdownFilter, RelatedDropdownFilter, RangeDateFilter
from simple_history.admin import SimpleHistoryAdmin
from utils.admin_helpers import jalali_column, JalaliAdminMixin
from .models import User, OTPCode, LoginHistory
from .forms import CustomAdminUserCreationForm


@admin.register(User)
class CustomUserAdmin(JalaliAdminMixin, BaseUserAdmin, ModelAdmin, SimpleHistoryAdmin):
    add_form = CustomAdminUserCreationForm
    list_display = (
        'display_user',
        'display_role',
        'display_phone',
        'display_national_code',
        'display_email',
        'display_active',
        'jalali_date_joined',
    )
    list_filter = (
        ('role', ChoicesDropdownFilter),
        ('specialties', RelatedDropdownFilter),
        'is_staff',
        'is_active',
        'is_superuser',
        'date_joined',
    )
    search_fields = (
        'username',
        'email',
        'first_name',
        'last_name',
        'phone_number',
        'national_code',
    )
    filter_horizontal = ('specialties', 'groups', 'user_permissions')
    ordering = ('-date_joined',)
    compressed_fields = True
    warn_unsaved_form = True

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        ('اطلاعات تکمیلی سیستم تهویه', {
            'fields': ('role', 'party', 'specialties', 'phone_number', 'national_code', 'avatar', 'must_change_password'),
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('jalali_last_login', 'jalali_date_joined')}),
    )

    add_fieldsets = (
        ("مشخصات حساب کاربری جدید", {
            'classes': ('wide',),
            'fields': (
                'phone_number',
                'username',
                'first_name',
                'last_name',
                'role',
                'party',
                'specialties',
                'national_code',
                'email',
                'avatar',
                'password',
                'password_confirm',
            ),
        }),
    )

    readonly_fields = ('jalali_date_joined', 'jalali_last_login')

    jalali_date_joined = jalali_column('date_joined', 'تاریخ عضویت')
    jalali_last_login = jalali_column('last_login', 'آخرین ورود')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            messages.success(
                request,
                format_html("کاربر <strong>{}</strong> با موفقیت در سامانه ذخیره شد.", obj.get_full_name() or obj.username)
            )

    @display(description="کاربر", header=True)
    def display_user(self, obj):
        full_name = obj.get_full_name()
        title = full_name if full_name else obj.username
        subtitle = f"@{obj.username}" if full_name else ""
        initial = (obj.first_name[:1] or obj.username[:1] or "؟").upper()
        if obj.avatar:
            avatar_info = {
                "path": obj.avatar.url,
                "squared": False,
                "borderless": False,
            }
            return [title, subtitle, initial, avatar_info]
        return [title, subtitle, initial]

    @display(
        description="نقش",
        label={
            User.Role.ADMIN: "danger",
            User.Role.EMPLOYEE: "warning",
            User.Role.CLIENT: "info",
            User.Role.PARTNER: "success",
        }
    )
    def display_role(self, obj):
        return obj.role, obj.get_role_display()

    @display(description="شماره موبایل")
    def display_phone(self, obj):
        if not obj.phone_number:
            return "—"
        return format_html('<span dir="ltr" class="font-mono text-sm">{}</span>', obj.phone_number)

    @display(description="کد ملی")
    def display_national_code(self, obj):
        if not obj.national_code:
            return "—"
        return format_html('<span dir="ltr" class="font-mono text-sm">{}</span>', obj.national_code)

    @display(description="ایمیل")
    def display_email(self, obj):
        return obj.email or "—"

    @display(description="فعال", boolean=True)
    def display_active(self, obj):
        return obj.is_active


@admin.register(OTPCode)
class OTPCodeAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'phone_number', 'purpose', 'user', 'is_used', 'attempt_count', 'jalali_expires_at', 'jalali_created_at')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('phone_number', 'user__username')
    exclude = ('used_at',)
    readonly_fields = ('code_hash', 'jalali_created_at', 'jalali_used_at')

    jalali_created_at = jalali_column('created_at', 'تاریخ ایجاد')
    jalali_expires_at = jalali_column('expires_at', 'تاریخ انقضا')
    jalali_used_at = jalali_column('used_at', 'تاریخ استفاده')


@admin.register(LoginHistory)
class LoginHistoryAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'user', 'username_attempted', 'result', 'ip_address', 'device_type', 'browser', 'os', 'jalali_created_at')
    list_filter = ('result', 'device_type', 'created_at')
    search_fields = ('username_attempted', 'user__username', 'ip_address', 'user_agent')
    readonly_fields = ('user', 'username_attempted', 'result', 'ip_address', 'user_agent', 'browser', 'os', 'device_type', 'jalali_created_at')

    jalali_created_at = jalali_column('created_at', 'تاریخ ثبت')
