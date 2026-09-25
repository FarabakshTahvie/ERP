from decimal import Decimal
from django import forms
from django.core.files.uploadedfile import UploadedFile
from unfold.forms import BaseDialogForm
from unfold.widgets import (
    UnfoldAdminTextInputWidget,
    UnfoldAdminDecimalFieldWidget,
)
from .models import Payment
from .services import PROOF_METHODS, proof_error, prepare_receipt_file


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


class PaymentInlineForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("method")
        receipt_file = cleaned_data.get("receipt_file")
        error = proof_error(
            method, has_file=bool(receipt_file),
            reference=(cleaned_data.get("reference_number") or "").strip(),
        )
        if error:
            raise forms.ValidationError(error)
        if isinstance(receipt_file, UploadedFile):
            try:
                cleaned_data["receipt_file"] = prepare_receipt_file(receipt_file)
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return cleaned_data
