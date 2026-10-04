from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("projects-table/", views.projects_table, name="projects_table"),
    path("stages/", views.stages_page, name="stages"),
    path("stages/table/", views.stages_table, name="stages_table"),
    path("stages/<int:stage_id>/assign/", views.assign_stage_page, name="assign_stage"),
    path("suspended/", views.suspended_page, name="suspended"),
    path("suspended/<int:stage_id>/resume/", views.suspended_resume, name="suspended_resume"),
    path("suspended/<int:stage_id>/cancel/", views.suspended_cancel, name="suspended_cancel"),
    path("notifications/", views.notifications_page, name="notifications"),
    path("notifications/table/", views.notifications_table, name="notifications_table"),
    path("notifications/<int:notification_id>/", views.notification_detail, name="notification_detail"),
    path("notifications/<int:notification_id>/resend/", views.notification_resend, name="notification_resend"),
]
