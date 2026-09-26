from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("inventory/stock-table/", views.stock_table, name="stock_table"),
    path("inventory/purchases/new/", views.purchase_new, name="purchase_new"),
    path("inventory/stock-movements/new/", views.stock_movement_new, name="stock_movement_new"),
]
