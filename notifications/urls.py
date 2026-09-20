from django.urls import re_path
from . import views

app_name = "notifications"

urlpatterns = [
    re_path(r"^s/(?P<code>[2-9a-z]{4,12})/?$", views.track_and_redirect, name="track_click"),
]
