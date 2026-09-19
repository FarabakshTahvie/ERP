from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import NotificationPolicy, Notification, NotificationClickEvent


@admin.register(NotificationPolicy)
class NotificationPolicyAdmin(ModelAdmin):
    list_display = ('notification_type', 'channel_policy', 'fallback_after_minutes')
    list_editable = ('channel_policy', 'fallback_after_minutes')


@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('id', 'notification_type', 'user', 'status', 'created_at', 'seen_at')
    list_filter = ('notification_type', 'status', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'title')
    readonly_fields = ('uuid', 'created_at', 'push_sent_at', 'sms_sent_at', 'seen_at')


@admin.register(NotificationClickEvent)
class NotificationClickEventAdmin(ModelAdmin):
    list_display = ('id', 'notification', 'channel', 'clicked_at', 'ip_address')
    list_filter = ('channel', 'clicked_at')
    readonly_fields = ('notification', 'channel', 'clicked_at', 'ip_address', 'user_agent')
