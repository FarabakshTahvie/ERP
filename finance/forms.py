from decimal import Decimal
from django import forms
from unfold.forms import BaseDialogForm
from unfold.widgets import (
    UnfoldAdminTextInputWidget,
    UnfoldAdminDecimalFieldWidget,
)


class AddInvoiceLineForm(BaseDialogForm):
    title = forms.CharField(
        max_length=200,
        label="عنوان هزینه",
        widget=UnfoldAdminTextInputWidget(),
    )
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=0,
        label="مبلغ (تومان)",
        widget=UnfoldAdminDecimalFieldWidget(),
    )
