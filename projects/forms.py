from django import forms
from unfold.forms import BaseDialogForm
from accounts.models import User


class StageCommentForm(BaseDialogForm):
    comment = forms.CharField(
        label="توضیحات / علت (اجباری)",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "دلیل کامل را وارد کنید..."}),
        required=True,
    )

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "").strip()
        if not comment:
            raise forms.ValidationError("ثبت توضیح اجباری است.")
        return comment


class StageAssignForm(BaseDialogForm):
    target_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        label="انتخاب مسئول جدید",
        required=True,
    )
    comment = forms.CharField(
        label="دلیل ارجاع دستی (اجباری)",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "دلیل ارجاع به این شخص..."}),
        required=True,
    )

    def clean_comment(self):
        comment = self.cleaned_data.get("comment", "").strip()
        if not comment:
            raise forms.ValidationError("ثبت دلیل ارجاع اجباری است.")
        return comment
