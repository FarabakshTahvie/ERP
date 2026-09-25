from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    path("portal/invoices/<uuid:invoice_uuid>/", views.invoice_detail, name="portal_invoice_detail"),
    path("portal/invoices/<uuid:invoice_uuid>/pdf/", views.invoice_pdf, name="portal_invoice_pdf"),
    path("portal/invoices/<uuid:invoice_uuid>/add-payment/", views.add_payment, name="portal_add_payment"),
    path("payments/", views.payments_review, name="payments_review"),
    path("payments/table/", views.payments_table, name="payments_table"),
    path("payments/<int:payment_id>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:payment_id>/decide/", views.payment_decide, name="payment_decide"),
]
