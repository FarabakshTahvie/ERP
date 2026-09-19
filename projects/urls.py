from django.urls import path
from . import views

app_name = "projects"

urlpatterns = [
    path("portal/<int:project_id>/progress/", views.project_progress, name="portal_project_progress"),
]
