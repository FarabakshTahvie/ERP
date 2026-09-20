from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("s/<str:code>/", views.track_and_redirect, name="track_click"),
]
