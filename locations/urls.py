from django.urls import path, re_path

from . import views

app_name = "locations"

urlpatterns = [
    path("locations/", views.location_list, name="list"),
    path("locations/new/", views.location_create, name="create"),
    path("locations/<int:pk>/save/", views.location_update, name="update"),
    path("locations/<int:pk>/delete/", views.location_delete, name="delete"),
    re_path(r"^loc/(?P<token>[0-9a-f]{32})/$", views.public_location, name="public"),
    re_path(r"^loc/(?P<token>[0-9a-f]{32})/image/$", views.public_location_image, name="public_image"),
]
