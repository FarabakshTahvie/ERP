from django.urls import path

from . import views, views_tasks

app_name = "messenger"

urlpatterns = [
    path("", views.page_inbox, name="inbox"),
    path("c/<int:conv_id>/", views.page_chat, name="chat"),
    path("profile/", views.page_profile, name="profile"),
    path("tasks/", views_tasks.page_tasks, name="tasks"),
    path("tasks/done/table/", views_tasks.done_table, name="tasks_done_table"),
    path("tasks/<int:task_id>/", views_tasks.task_detail, name="task_detail"),
    path("api/inbox/", views.api_inbox, name="api_inbox"),
    path("api/open/<int:user_id>/", views.api_open, name="api_open"),
    path("api/c/<int:conv_id>/messages/", views.api_messages, name="api_messages"),
    path("api/c/<int:conv_id>/send/", views.api_send, name="api_send"),
    path("api/c/<int:conv_id>/upload/", views.api_upload, name="api_upload"),
    path("api/c/<int:conv_id>/read/", views.api_read, name="api_read"),
    path("api/c/<int:conv_id>/mute/", views.api_mute, name="api_mute"),
    path("api/m/<int:message_id>/edit/", views.api_edit, name="api_edit"),
    path("api/m/<int:message_id>/delete/", views.api_delete, name="api_delete"),
    path("api/m/<int:message_id>/pin/", views.api_pin, name="api_pin"),
]
