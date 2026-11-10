from django.urls import path

from . import views_manage

app_name = "catalog"

urlpatterns = [
    path("catalog/manage/<str:kind>/<int:obj_id>/", views_manage.manage, name="manage"),
    path("catalog/manage/<str:kind>/<int:obj_id>/save/", views_manage.manage_save, name="manage_save"),
    path("catalog/manage/<str:kind>/<int:obj_id>/cover/", views_manage.manage_cover, name="manage_cover"),
    path("catalog/manage/<str:kind>/<int:obj_id>/media/", views_manage.media_upload, name="media_upload"),
    path("catalog/media/<int:media_id>/delete/", views_manage.media_delete, name="media_delete"),
]
