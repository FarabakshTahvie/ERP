from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("projects-table/", views.projects_table, name="projects_table"),
    path("stages/", views.stages_page, name="stages"),
    path("stages/table/", views.stages_table, name="stages_table"),
    path("stages/<int:stage_id>/assign/", views.assign_stage_page, name="assign_stage"),
    path("stages/<int:stage_id>/suspend/", views.stage_suspend, name="stage_suspend"),
    path("suspended/", views.suspended_page, name="suspended"),
    path("suspended/table/", views.suspended_table, name="suspended_table"),
    path("cancelled/table/", views.cancelled_table, name="cancelled_table"),
    path("held/<int:project_id>/", views.held_detail, name="held_detail"),
    path("held/<int:project_id>/restore/", views.project_restore, name="project_restore"),
    path("suspended/<int:stage_id>/resume/", views.suspended_resume, name="suspended_resume"),
    path("suspended/<int:stage_id>/cancel/", views.suspended_cancel, name="suspended_cancel"),
    path("notifications/", views.notifications_page, name="notifications"),
    path("notifications/table/", views.notifications_table, name="notifications_table"),
    path("notifications/<int:notification_id>/", views.notification_detail, name="notification_detail"),
    path("notifications/<int:notification_id>/resend/", views.notification_resend, name="notification_resend"),
]
