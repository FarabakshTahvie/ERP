import re
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.urls import reverse_lazy
from django_htmx.http import HttpResponseClientRedirect

from .forms import StaffRegistrationForm
from .models import User, OTPCode
from .services import create_staff_account
from utils.sms import SMSService


def is_manager(user):
    return user.is_authenticated and user.role == User.Role.ADMIN


class StyledLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def request_otp_login(request):
    phone_number = request.POST.get("phone_number", "").strip()
    if not phone_number:
        return render(request, "accounts/partials/otp_error.html", {"message": "لطفاً شماره موبایل خود را وارد کنید."})
    if not re.match(r"^09\d{9}$", phone_number):
        return render(request, "accounts/partials/otp_error.html", {"message": "فرمت شماره موبایل معتبر نیست (مثال: 09123456789)."})
    if not User.objects.filter(phone_number=phone_number).exists():
        return render(request, "accounts/partials/otp_error.html", {"message": "کاربری با این شماره موبایل در سامانه ثبت نشده است."})

    otp, raw_code = OTPCode.generate(phone_number=phone_number, purpose=OTPCode.Purpose.LOGIN)
    SMSService().send_otp(mobile=phone_number, code=raw_code)
    next_url = request.POST.get("next", "")
    return render(request, "accounts/partials/otp_verify_form.html", {"phone_number": phone_number, "next": next_url})


def verify_otp_login(request):
    phone_number = request.POST.get("phone_number", "").strip()
    code = request.POST.get("code", "").strip()
    if not code:
        return render(request, "accounts/partials/otp_error.html", {"message": "لطفاً کد تایید را وارد نمایید."})

    ok, result = OTPCode.verify(phone_number, OTPCode.Purpose.LOGIN, code)
    if not ok:
        return render(request, "accounts/partials/otp_error.html", {"message": result})

    user = User.objects.filter(phone_number=phone_number).first()
    if not user:
        return render(request, "accounts/partials/otp_error.html", {"message": "اطلاعات حساب کاربری یافت نشد."})

    auth_login(request, user)
    next_url = request.POST.get("next") or "/"
    return HttpResponseClientRedirect(next_url)


@login_required
@user_passes_test(is_manager)
def register_staff(request):
    if request.method == "POST":
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user, raw_password = create_staff_account(**form.cleaned_data)
            return render(request, "accounts/staff_registered.html", {"user": user, "raw_password": raw_password})
    else:
        form = StaffRegistrationForm()
    return render(request, "accounts/register_staff.html", {"form": form})


def request_password_reset(request):
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", "").strip()
        user = User.objects.filter(phone_number=phone_number).first()
        if user:
            otp, raw_code = OTPCode.generate(phone_number=phone_number, purpose=OTPCode.Purpose.PASSWORD_RESET, user=user)
            SMSService().send_otp(mobile=phone_number, code=raw_code)
        return render(request, "accounts/password_reset_sent.html", {"phone_number": phone_number})
    return render(request, "accounts/password_reset_request.html")


def verify_password_reset(request):
    phone_number = request.POST.get("phone_number", "").strip()
    code = request.POST.get("code", "").strip()
    new_password = request.POST.get("new_password", "").strip()

    if not new_password or len(new_password) < 6:
        return render(request, "accounts/password_reset_sent.html", {"phone_number": phone_number, "error": "رمز عبور جدید باید حداقل ۶ کاراکتر باشد."})

    ok, result = OTPCode.verify(phone_number, OTPCode.Purpose.PASSWORD_RESET, code)
    if not ok:
        return render(request, "accounts/password_reset_sent.html", {"phone_number": phone_number, "error": result})

    user = User.objects.filter(phone_number=phone_number).first()
    if not user:
        return render(request, "accounts/password_reset_sent.html", {"phone_number": phone_number, "error": "کاربری با این شماره یافت نشد."})

    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    return redirect("accounts:login")


class StyledPasswordChangeView(PasswordChangeView):
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        return response
