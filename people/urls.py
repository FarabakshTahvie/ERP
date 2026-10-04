from django.urls import path
from . import views

app_name = "people"

urlpatterns = [
    path("", views.staff_page, name="staff"),
    path("table/", views.staff_table, name="staff_table"),
    path("customers/", views.customers_page, name="customers"),
    path("customers/table/", views.customers_table, name="customers_table"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:user_id>/reset-password/", views.user_reset_password, name="user_reset_password"),
    path("users/<int:user_id>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    path("parties/<int:party_id>/", views.party_detail, name="party_detail"),
    path("parties/<int:party_id>/edit/", views.party_edit, name="party_edit"),
]
