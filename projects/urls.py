from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("staff/projects/<int:project_id>/edit/", views.project_edit, name="project_edit"),
    path("staff/projects/<int:project_id>/overview/", views.staff_project_overview, name="staff_project_overview"),
    path("portal/approvals/<int:approval_id>/", views.portal_stage_approval, name="portal_stage_approval"),
    path("portal/<int:project_id>/progress/", views.project_progress, name="portal_project_progress"),
    path("my-tasks/", views.my_tasks, name="my_tasks"),
    path("my-tasks/<int:stage_id>/", views.my_task_detail, name="my_task_detail"),
    path("my-tasks/<int:stage_id>/claim/", views.my_task_claim, name="my_task_claim"),
    path("my-tasks/<int:stage_id>/complete/", views.my_task_complete, name="my_task_complete"),
    path("my-tasks/<int:stage_id>/transfer/", views.my_task_transfer, name="my_task_transfer"),
    path("new-project/", views.new_project_form, name="new_project_form"),
    path("new-project/party-search/", views.new_project_party_search, name="new_project_party_search"),
    path("new-project/submit/", views.new_project_submit, name="new_project_submit"),
    path("dashboard/my-tasks-table/", views.dashboard_my_tasks_table, name="dashboard_my_tasks_table"),
    path("dashboard/claimable-table/", views.dashboard_claimable_table, name="dashboard_claimable_table"),
    path("dashboard/completed-table/", views.dashboard_completed_table, name="dashboard_completed_table"),
    path("dashboard/my-projects-table/", views.dashboard_my_projects_table, name="dashboard_my_projects_table"),
]
