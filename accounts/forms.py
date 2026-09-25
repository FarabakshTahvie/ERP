import re
from django import forms
from django.core.exceptions import ValidationError
from unfold.widgets import (
    UnfoldAdminTextInputWidget,
    UnfoldAdminPasswordWidget,
    UnfoldAdminPasswordToggleWidget,
)
from .models import User
from core.models import Specialty
from utils.utils import generate_random_code, is_valid_national_code


class CustomAdminUserCreationForm(forms.ModelForm):
    """
    فرم اختصاصی افزودن کاربر در پنل مدیریت.
    - تولید خودکار رمز عبور تصادفی و امن در صورت خالی گذاشتن فیلدها
    - تنظیم خودکار نام کاربری برابر با شماره موبایل در صورت خالی بودن
    - اعتبارسنجی دقیق و نمایش خطاهای خوانای فارسی
    """
    username = forms.CharField(
        label="نام کاربری",
        widget=UnfoldAdminTextInputWidget(),
        required=False,
        help_text="اختیاری — در صورت خالی ماندن، شماره موبایل کاربر درج می‌شود.",
    )
    password = forms.CharField(
        label="رمز عبور",
        widget=UnfoldAdminPasswordToggleWidget(attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="اختیاری — اگر خالی بگذارید، رمز عبور تصادفی و امن به صورت خودکار ایجاد خواهد شد.",
    )
    password_confirm = forms.CharField(
        label="تکرار رمز عبور",
        widget=UnfoldAdminPasswordToggleWidget(attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="در صورت وارد کردن رمز عبور به صورت دستی، تکرار آن الزامی است.",
    )

    class Meta:
        model = User
        fields = (
            "phone_number",
            "username",
            "first_name",
            "last_name",
            "role",
            "party",
            "specialties",
            "national_code",
            "email",
            "avatar",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["phone_number"].required = True
        self.fields["role"].initial = User.Role.CLIENT

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if not phone:
            raise ValidationError("شماره موبایل الزامی است.")
        if not re.match(r"^09\d{9}$", phone):
            raise ValidationError("شماره موبایل معتبر نیست (باید ۱۱ رقم بوده و با 09 شروع شود).")
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("کاربری با این شماره موبایل قبلاً در سامانه ثبت شده است.")
        return phone

    def clean_national_code(self):
        code = (self.cleaned_data.get("national_code") or "").strip()
        if code:
            if not is_valid_national_code(code):
                raise ValidationError("کد ملی وارد شده معتبر نمی‌باشد (فرمت یا رقم کنترلی نادرست است).")
            if User.objects.filter(national_code=code).exists():
                raise ValidationError("این کد ملی قبلاً برای کاربر دیگری در سامانه ثبت شده است.")
        return code or None

    def clean_username(self):
        uname = (self.cleaned_data.get("username") or "").strip()
        return uname

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get("phone_number")
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        target_username = username if username else phone
        if target_username and User.objects.filter(username=target_username).exists():
            self.add_error("username", "این نام کاربری قبلاً در سامانه ثبت شده است.")

        if password or password_confirm:
            if not password:
                self.add_error("password", "لطفاً رمز عبور را وارد کنید.")
            elif not password_confirm:
                self.add_error("password_confirm", "لطفاً تکرار رمز عبور را وارد کنید.")
            elif password != password_confirm:
                self.add_error("password_confirm", "رمز عبور با تکرار آن یکسان نیست.")
            elif len(password) < 6:
                self.add_error("password", "طول رمز عبور باید حداقل ۶ کاراکتر باشد.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.username:
            user.username = user.phone_number

        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        else:
            raw_password = generate_random_code(length=8, digits_only=False)
            user.set_password(raw_password)

        user.must_change_password = False

        if user.role in [User.Role.ADMIN, User.Role.EMPLOYEE]:
            user.is_staff = True

        if commit:
            user.save()
            self.save_m2m()
        return user


class StaffRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=150,
        label="نام",
        widget=forms.TextInput(attrs={'class': 'input w-full', 'placeholder': 'نام'})
    )
    last_name = forms.CharField(
        max_length=150,
        label="نام خانوادگی",
        widget=forms.TextInput(attrs={'class': 'input w-full', 'placeholder': 'نام خانوادگی'})
    )
    phone_number = forms.CharField(
        max_length=11,
        label="شماره موبایل",
        widget=forms.TextInput(attrs={
            'class': 'input w-full font-technical', 'placeholder': '09123456789',
            'inputmode': 'numeric', 'autocomplete': 'off',
        })
    )
    role = forms.ChoiceField(
        choices=[(User.Role.ADMIN, "مدیر"), (User.Role.EMPLOYEE, "تکنسین")],
        label="نقش",
        widget=forms.Select(attrs={'class': 'select w-full'})
    )
    specialties = forms.ModelMultipleChoiceField(
        queryset=Specialty.objects.filter(is_active=True),
        required=False,
        label="تخصص‌ها",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'sr-only'})
    )

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if not re.match(r"^09\d{9}$", phone):
            raise forms.ValidationError("شماره موبایل معتبر نیست (باید ۱۱ رقم بوده و با 09 شروع شود).")
        if User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("کاربری با این شماره موبایل قبلاً در سامانه ثبت شده است.")
        return phone
