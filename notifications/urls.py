from django.urls import path
from .views import track_and_redirect

app_name = "notifications"
urlpatterns = [
    path("n/<uuid:notification_uuid>/", track_and_redirect, name="track_click"),
]
