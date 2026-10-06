from django.urls import path
from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.task_list, name="list"),
    path("open/table/", views.open_table, name="open_table"),
    path("done/table/", views.done_table, name="done_table"),
    path("save/", views.task_save, name="save"),
    path("<int:task_id>/save/", views.task_save, name="save"),
    path("<int:task_id>/", views.task_detail, name="detail"),
    path("<int:task_id>/edit/", views.task_edit, name="edit"),
    path("<int:task_id>/attachments/", views.attachment_upload, name="attachment_upload"),
    path("attachments/<int:attachment_id>/delete/", views.attachment_delete, name="attachment_delete"),
    path("<int:task_id>/check/", views.task_check, name="check"),
    path("<int:task_id>/submit/", views.task_submit, name="submit"),
    path("my/panel/", views.my_panel, name="my_panel"),
    path("my/done-panel/", views.my_done_panel, name="done_panel"),
]
