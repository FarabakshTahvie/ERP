from django.urls import path
from . import views, views_ops

app_name = "projects"

urlpatterns = [
    path("staff/stages/<int:stage_id>/ship-check/", views_ops.ship_check, name="ship_check"),
    path("staff/stages/<int:stage_id>/install-line/", views_ops.install_line, name="install_line"),
    path("staff/stages/<int:stage_id>/extras/add/", views_ops.extra_add, name="extra_add"),
    path("staff/extras/<int:extra_id>/delete/", views_ops.extra_delete, name="extra_delete"),
    path("staff/stages/<int:stage_id>/part-request/", views_ops.part_request_create, name="part_request_create"),
    path("staff/part-requests/<int:req_id>/cancel/", views_ops.part_request_cancel, name="part_request_cancel"),
    path("staff/part-requests/<int:req_id>/", views_ops.part_request_detail, name="part_request_detail"),
    path("staff/part-requests/<int:req_id>/decide/", views_ops.part_request_decide, name="part_request_decide"),
    path("dashboard/part-requests-table/", views_ops.part_requests_table, name="part_requests_table"),
    path("staff/projects/<int:project_id>/costs/add/", views_ops.cost_add, name="cost_add"),
    path("staff/costs/<int:cost_id>/delete/", views_ops.cost_delete, name="cost_delete"),
    path("staff/projects/<int:project_id>/final-review/", views_ops.final_review, name="final_review"),
    path("staff/projects/<int:project_id>/move-stage/", views_ops.move_stage, name="move_stage"),
    path("staff/projects/<int:project_id>/edit/", views.project_edit, name="project_edit"),
    path("staff/projects/<int:project_id>/proforma/", views.proforma_editor, name="proforma_editor"),
    path("staff/projects/<int:project_id>/overview/", views.staff_project_overview, name="staff_project_overview"),
    path("staff/stages/<int:stage_id>/files/", views.stage_file_upload, name="stage_file_upload"),
    path("staff/files/<int:file_id>/cut/", views.cut_set, name="cut_set"),
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
