from django.urls import path
from . import views, views_accounting

app_name = "finance"

urlpatterns = [
    path("accounting/", views_accounting.overview, name="accounting_overview"),
    path("accounting/projects/", views_accounting.projects_page, name="accounting_projects"),
    path("accounting/projects/table/", views_accounting.projects_table, name="accounting_projects_table"),
    path("accounting/projects/<int:project_id>/", views_accounting.project_detail, name="accounting_project"),
    path("accounting/projects/<int:project_id>/cost/", views_accounting.project_add_cost, name="accounting_add_cost"),
    path("accounting/costs/<int:cost_id>/delete/", views_accounting.project_delete_cost, name="accounting_delete_cost"),
    path("accounting/projects/<int:project_id>/invoice-adjust/", views_accounting.project_adjust_invoice, name="accounting_adjust_invoice"),
    path("payments/<int:payment_id>/settle-credit/", views_accounting.credit_settle, name="payment_settle_credit"),
    path("accounting/stock/", views_accounting.stock_page, name="accounting_stock"),
    path("accounting/stock/table/", views_accounting.stock_table, name="accounting_stock_table"),
    path("accounting/purchases/", views_accounting.purchases_page, name="accounting_purchases"),
    path("accounting/purchases/table/", views_accounting.purchases_table, name="accounting_purchases_table"),
    path("portal/invoices/<uuid:invoice_uuid>/", views.invoice_detail, name="portal_invoice_detail"),
    path("portal/invoices/<uuid:invoice_uuid>/pdf/", views.invoice_pdf, name="portal_invoice_pdf"),
    path("portal/invoices/<uuid:invoice_uuid>/add-payment/", views.add_payment, name="portal_add_payment"),
    path("payments/", views.payments_review, name="payments_review"),
    path("payments/table/", views.payments_table, name="payments_table"),
    path("payments/<int:payment_id>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:payment_id>/decide/", views.payment_decide, name="payment_decide"),
]
