from django.urls import path
from . import views

app_name = "finance"

urlpatterns = [
    path("portal/invoices/<uuid:invoice_uuid>/", views.invoice_detail, name="portal_invoice_detail"),
    path("portal/invoices/<uuid:invoice_uuid>/pdf/", views.invoice_pdf, name="portal_invoice_pdf"),
]
