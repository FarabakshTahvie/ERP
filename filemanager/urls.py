from django.urls import path, re_path

from . import views

app_name = "filemanager"

urlpatterns = [
    path("files/", views.file_list, name="list"),
    path("files/upload/", views.file_upload, name="upload"),
    path("files/<int:pk>/visibility/", views.file_visibility, name="visibility"),
    path("files/<int:pk>/delete/", views.file_delete, name="delete"),
    re_path(r"^f/(?P<code>[2-9a-z]{6,12})/$", views.file_open, name="open"),
]
