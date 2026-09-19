from django.db import transaction
from django.core.exceptions import ValidationError
from utils.utils import generate_random_code
from .models import User


@transaction.atomic
def create_staff_account(*, first_name, last_name, phone_number, role, specialties=None):
    """ایجاد حساب کاربری پرسنل/تکنسین با رمز عبور تصادفی و نام کاربری منطبق بر شماره موبایل."""
    if User.objects.filter(phone_number=phone_number).exists():
        raise ValidationError("کاربری با این شماره موبایل قبلاً در سامانه ثبت شده است.")
    if User.objects.filter(username=phone_number).exists():
        raise ValidationError("نام کاربری مربوط به این شماره موبایل قبلاً ثبت شده است.")

    raw_password = generate_random_code(length=10, digits_only=False)
    user = User(
        username=phone_number,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone_number,
        role=role,
        is_staff=True,
        must_change_password=False,
    )
    user.set_password(raw_password)
    user.save()
    if specialties:
        user.specialties.set(specialties)
    return user, raw_password
