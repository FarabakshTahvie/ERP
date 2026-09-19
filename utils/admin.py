from django.contrib import admin
from django.contrib import messages
from unfold.admin import ModelAdmin
from .models import PushDevice


@admin.register(PushDevice)
class PushDeviceAdmin(ModelAdmin):
    """
    Unfold Admin configuration for PushDevice model with actions to test push and activate/deactivate.
    """
    list_display = (
        'id',
        'user',
        'name',
        'type',
        'short_token',
        'browser',
        'os',
        'is_active',
        'created_at',
    )
    list_filter = (
        'type',
        'is_active',
        'browser',
        'os',
        'created_at',
    )
    search_fields = (
        'registration_id',
        'name',
        'user__username',
        'user__phone_number',
        'user__first_name',
        'user__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')
    actions = ['send_test_push', 'activate_devices', 'deactivate_devices']

    def short_token(self, obj):
        return f"{obj.registration_id[:20]}..." if obj.registration_id else "—"
    short_token.short_description = "خلاصه توکن"

    @admin.action(description="ارسال پوش تستی به دستگاه‌های انتخاب‌شده")
    def send_test_push(self, request, queryset):
        active_devices = queryset.filter(is_active=True)
        count = active_devices.count()
        if count == 0:
            self.message_user(request, "هیچ دستگاه فعالی در بین موارد انتخاب شده وجود ندارد.", level=messages.WARNING)
            return

        res = active_devices.send_message(
            title="تست سامانه فرابخش",
            body="این یک پوش نوتیفیکیشن آزمایشی از پنل مدیریت فرابخش است.",
        )
        if res.get("success"):
            self.message_user(request, f"نوتیفیکیشن تستی با موفقیت به {count} دستگاه ارسال شد.", level=messages.SUCCESS)
        else:
            self.message_user(request, f"ارسال نوتیفیکیشن با خطا مواجه شد: {res.get('error') or res.get('data')}", level=messages.ERROR)

    @admin.action(description="فعال‌سازی دستگاه‌های انتخاب‌شده")
    def activate_devices(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} دستگاه فعال شد.", level=messages.SUCCESS)

    @admin.action(description="غیرفعال‌سازی دستگاه‌های انتخاب‌شده")
    def deactivate_devices(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} دستگاه غیرفعال شد.", level=messages.SUCCESS)
