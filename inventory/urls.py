from django.urls import path
from . import views, views_bulk

app_name = "inventory"

urlpatterns = [
    path("inventory/items/new/", views.item_new, name="item_new"),
    path("inventory/items/quick-create/", views.item_quick_create, name="item_quick_create"),
    path("inventory/items/<int:item_id>/edit/", views.item_edit, name="item_edit"),
    path("inventory/items/<int:item_id>/toggle-active/", views.item_toggle_active, name="item_toggle_active"),
    path("inventory/stock-table/", views.stock_table, name="stock_table"),
    path("inventory/purchases/new/", views.purchase_new, name="purchase_new"),
    path("inventory/stock-movements/new/", views.stock_movement_new, name="stock_movement_new"),
    path("inventory/bulk-opening/", views_bulk.bulk_opening_page, name="bulk_opening"),
    path("inventory/bulk-reconciliation/", views_bulk.bulk_reconciliation_page, name="bulk_reconciliation"),
]
