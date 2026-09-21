from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from utils.admin_helpers import jalali_column, JalaliAdminMixin
from .models import NotificationPolicy, Notification, NotificationClickEvent


class NotificationClickEventInline(JalaliAdminMixin, TabularInline):
    model = NotificationClickEvent
    extra = 0
    readonly_fields = ('channel', 'jalali_clicked_at', 'ip_address', 'user_agent')
    can_delete = False

    jalali_clicked_at = jalali_column('clicked_at', 'زمان کلیک')


@admin.register(NotificationPolicy)
class NotificationPolicyAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('notification_type', 'channel_policy', 'fallback_after_minutes')
    list_editable = ('channel_policy', 'fallback_after_minutes')


@admin.register(Notification)
class NotificationAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'notification_type', 'user', 'short_code', 'status', 'jalali_created_at', 'jalali_seen_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'title', 'short_code')
    exclude = ('seen_at', 'push_sent_at', 'sms_sent_at')
    readonly_fields = ('uuid', 'short_code', 'jalali_created_at', 'jalali_push_sent_at', 'jalali_sms_sent_at', 'jalali_seen_at')
    inlines = [NotificationClickEventInline]

    jalali_created_at = jalali_column('created_at', 'تاریخ ایجاد')
    jalali_seen_at = jalali_column('seen_at', 'تاریخ مشاهده')
    jalali_push_sent_at = jalali_column('push_sent_at', 'زمان ارسال پوش')
    jalali_sms_sent_at = jalali_column('sms_sent_at', 'زمان ارسال پیامک')


@admin.register(NotificationClickEvent)
class NotificationClickEventAdmin(JalaliAdminMixin, ModelAdmin):
    list_display = ('id', 'notification', 'channel', 'jalali_clicked_at', 'ip_address')
    list_filter = ('channel', 'clicked_at')
    readonly_fields = ('notification', 'channel', 'jalali_clicked_at', 'ip_address', 'user_agent')

    jalali_clicked_at = jalali_column('clicked_at', 'زمان کلیک')
