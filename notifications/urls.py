from django.urls import path, re_path
from . import views

app_name = "notifications"

urlpatterns = [
    path("notifications/", views.center, name="center"),
    path("notifications/seen/", views.mark_all_seen, name="mark_all_seen"),
    re_path(r"^s/(?P<code>[2-9a-z]{4,12})/?$", views.track_and_redirect, name="track_click"),
]
