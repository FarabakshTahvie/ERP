from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import ChoicesDropdownFilter, RelatedDropdownFilter, RangeDateFilter
from simple_history.admin import SimpleHistoryAdmin
from .models import User, OTPCode, LoginHistory
from .forms import CustomAdminUserCreationForm


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin, SimpleHistoryAdmin):
    add_form = CustomAdminUserCreationForm
    list_display = (
        'display_user',
        'display_role',
        'display_phone',
        'display_national_code',
        'display_email',
        'display_active',
        'date_joined',
    )
    list_filter = (
        ('role', ChoicesDropdownFilter),
        ('specialties', RelatedDropdownFilter),
        'is_staff',
        'is_active',
        'is_superuser',
        ('date_joined', RangeDateFilter),
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
            'fields': ('role', 'party', 'specialties', 'phone_number', 'national_code', 'avatar', 'avatar_preview', 'must_change_password'),
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
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

    readonly_fields = ('avatar_preview', 'date_joined', 'last_login')

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
        if obj.avatar:
            avatar_info = {
                "path": obj.avatar.url,
                "squared": False,
                "borderless": False,
                "width": 32,
                "height": 32,
            }
            return [title, subtitle, avatar_info]
        initial = (obj.first_name[:1] or obj.username[:1] or "؟").upper()
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

    def avatar_tag(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" width="36" height="36" style="border-radius: 50%; object-fit: cover;" />', obj.avatar.url)
        return "—"
    avatar_tag.short_description = "تصویر پروفایل"

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" width="140" height="140" style="border-radius: 12px; object-fit: cover; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);" />', obj.avatar.url)
        return "تصویری آپلود نشده است"
    avatar_preview.short_description = "پیش‌نمایش تصویر پروفایل"


@admin.register(OTPCode)
class OTPCodeAdmin(ModelAdmin):
    list_display = ('id', 'phone_number', 'purpose', 'user', 'is_used', 'attempt_count', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_used', 'created_at')
    search_fields = ('phone_number', 'user__username')
    readonly_fields = ('code_hash', 'created_at', 'used_at')


@admin.register(LoginHistory)
class LoginHistoryAdmin(ModelAdmin):
    list_display = ('id', 'user', 'username_attempted', 'result', 'ip_address', 'device_type', 'browser', 'os', 'created_at')
    list_filter = ('result', 'device_type', 'created_at')
    search_fields = ('username_attempted', 'user__username', 'ip_address', 'user_agent')
    readonly_fields = ('user', 'username_attempted', 'result', 'ip_address', 'user_agent', 'browser', 'os', 'device_type', 'created_at')
