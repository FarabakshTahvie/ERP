from django import forms
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.contrib import messages
from unfold.forms import BaseDialogForm


class StageAdvanceForm(BaseDialogForm):
    comment = forms.CharField(
        label="توضیحات و دلایل (اجباری)",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "توضیح کامل در مورد این تغییر وضعیت..."}),
        required=True,
    )

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "").strip()
        if not comment:
            raise forms.ValidationError("ثبت توضیح برای این تغییر وضعیت اجباری است.")
        return comment
