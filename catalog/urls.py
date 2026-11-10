from django.urls import path

from . import views_manage, views_public

app_name = "catalog"

urlpatterns = [
    path("services/", views_public.service_list, name="service_list"),
    path("services/more/", views_public.service_list_more, name="service_list_more"),
    path("services/<int:pk>/", views_public.service_detail, name="service_detail"),
    path("products/", views_public.item_list, name="item_list"),
    path("products/more/", views_public.item_list_more, name="item_list_more"),
    path("products/<int:pk>/", views_public.item_detail, name="item_detail"),
    path("catalog/manage/<str:kind>/<int:obj_id>/", views_manage.manage, name="manage"),
    path("catalog/manage/<str:kind>/<int:obj_id>/save/", views_manage.manage_save, name="manage_save"),
    path("catalog/manage/<str:kind>/<int:obj_id>/cover/", views_manage.manage_cover, name="manage_cover"),
    path("catalog/manage/<str:kind>/<int:obj_id>/media/", views_manage.media_upload, name="media_upload"),
    path("catalog/media/<int:media_id>/delete/", views_manage.media_delete, name="media_delete"),
]
