from django.urls import path

from . import views

app_name = "messenger"

urlpatterns = [
    path("", views.page_inbox, name="inbox"),
    path("c/<int:conv_id>/", views.page_chat, name="chat"),
    path("api/inbox/", views.api_inbox, name="api_inbox"),
    path("api/open/<int:user_id>/", views.api_open, name="api_open"),
    path("api/c/<int:conv_id>/messages/", views.api_messages, name="api_messages"),
    path("api/c/<int:conv_id>/send/", views.api_send, name="api_send"),
    path("api/c/<int:conv_id>/read/", views.api_read, name="api_read"),
    path("api/c/<int:conv_id>/mute/", views.api_mute, name="api_mute"),
    path("api/m/<int:message_id>/edit/", views.api_edit, name="api_edit"),
    path("api/m/<int:message_id>/delete/", views.api_delete, name="api_delete"),
    path("api/m/<int:message_id>/pin/", views.api_pin, name="api_pin"),
]
