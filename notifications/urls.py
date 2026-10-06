from django.urls import path, re_path
from . import views, broadcast_views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.center, name="center"),
    path("notifications/seen/", views.mark_all_seen, name="mark_all_seen"),
    re_path(r"^s/(?P<code>[2-9a-z]{4,12})/?$", views.track_and_redirect, name="track_click"),

    # بخش ارسال پیام همگانی
    path("broadcast/", broadcast_views.broadcast_form, name="broadcast_form"),
    path("broadcast/preview/", broadcast_views.broadcast_preview, name="broadcast_preview"),
    path("broadcast/history/", broadcast_views.broadcast_history, name="broadcast_history"),
    path("broadcast/history/table/", broadcast_views.broadcast_history_table, name="broadcast_history_table"),
    path("broadcast/<int:broadcast_id>/", broadcast_views.broadcast_detail, name="broadcast_detail"),
    path("broadcast/<int:broadcast_id>/table/", broadcast_views.broadcast_detail_table, name="broadcast_detail_table"),
    path("broadcast/<int:broadcast_id>/retry/", broadcast_views.broadcast_retry, name="broadcast_retry"),
]
