import re
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from django_htmx.http import HttpResponseClientRedirect

from .forms import StaffRegistrationForm
from .models import User, OTPCode
from .services import create_staff_account, get_or_create_active_otp, otp_remaining_seconds
from utils.sms import SMSService
from utils.request_meta import get_client_ip

OTP_LOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"


def is_manager(user):
    return user.is_authenticated and user.role == User.Role.ADMIN


class StyledLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


def _otp_ip_rate_limit_error(request):
    """
    محدودیت فقط روی آی‌پی و فقط وقتی واقعاً قراره پیامک تازه ارسال شود (نه هر بار
    که کاربر فقط وضعیت کد فعلی را چک می‌کند). cache.incr اتمیک است.
    """
    ip_key = f"otp:ip:{get_client_ip(request) or 'unknown'}"
    cache.add(ip_key, 0, timeout=3600)
    if cache.incr(ip_key) > 10:
        return "تعداد درخواست‌ها زیاد است. لطفاً بعداً دوباره تلاش کنید."
    return None


@require_POST
def request_otp_login(request):
    phone_number = request.POST.get("phone_number", "").strip()
    next_url = request.POST.get("next", "")

    if not phone_number:
        return render(request, "accounts/partials/otp_phone_form.html", {
            "error": "لطفاً شماره موبایل خود را وارد کنید.", "next": next_url,
        })
    if not re.match(r"^09\d{9}$", phone_number):
        return render(request, "accounts/partials/otp_phone_form.html", {
            "error": "فرمت شماره موبایل معتبر نیست (مثال: 09123456789).",
            "phone_number": phone_number, "next": next_url,
        })
    if not User.objects.filter(phone_number=phone_number, is_active=True).exists():
        return render(request, "accounts/partials/otp_phone_form.html", {
            "error": "کاربری با این شماره موبایل در سامانه ثبت نشده است.",
            "phone_number": phone_number, "next": next_url,
        })

    otp, raw_code, is_new = get_or_create_active_otp(phone_number, OTPCode.Purpose.LOGIN)

    if is_new:
        error = _otp_ip_rate_limit_error(request)
        if error:
            otp.delete()
            return render(request, "accounts/partials/otp_phone_form.html", {
                "error": error, "phone_number": phone_number, "next": next_url,
            })
        result = SMSService().send_otp(mobile=phone_number, code=raw_code)
        if not result.get("success"):
            otp.delete()
            return render(request, "accounts/partials/otp_phone_form.html", {
                "error": "ارسال پیامک ناموفق بود، دوباره تلاش کنید.",
                "phone_number": phone_number, "next": next_url,
            })

    remaining = max(int((otp.expires_at - timezone.now()).total_seconds()), 0)
    return render(request, "accounts/partials/otp_verify_form.html", {
        "phone_number": phone_number, "next": next_url,
        "remaining_seconds": remaining, "resent": not is_new,
    })


def otp_login_phone_form(request):
    """برای دکمه‌ی «ویرایش شماره»: فرم شماره را از نو (تمیز) برمی‌گرداند."""
    next_url = request.GET.get("next", "")
    return render(request, "accounts/partials/otp_phone_form.html", {"next": next_url})


@require_POST
def verify_otp_login(request):
    phone_number = request.POST.get("phone_number", "").strip()
    code = request.POST.get("code", "").strip()
    next_url = request.POST.get("next", "")

    common_ctx = {
        "phone_number": phone_number, "next": next_url,
        "remaining_seconds": otp_remaining_seconds(phone_number, OTPCode.Purpose.LOGIN),
    }

    if not code:
        return render(request, "accounts/partials/otp_verify_form.html", {
            **common_ctx, "error": "لطفاً کد تایید را وارد نمایید.",
        })

    ok, result = OTPCode.verify(phone_number, OTPCode.Purpose.LOGIN, code)
    if not ok:
        return render(request, "accounts/partials/otp_verify_form.html", {**common_ctx, "error": result})

    user = User.objects.filter(phone_number=phone_number, is_active=True).first()
    if not user:
        return render(request, "accounts/partials/otp_verify_form.html", {
            **common_ctx, "error": "اطلاعات حساب کاربری یافت نشد.",
        })

    auth_login(request, user, backend=OTP_LOGIN_BACKEND)
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = "/"
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
        if not re.match(r"^09\d{9}$", phone_number):
            return render(request, "accounts/partials/pwreset_phone_form.html", {
                "error": "فرمت شماره موبایل معتبر نیست.", "phone_number": phone_number,
            })

        user = User.objects.filter(phone_number=phone_number, is_active=True).first()
        remaining = 0
        resent = False

        # نکته‌ی امنیتی: چه کاربر با این شماره وجود داشته باشد چه نه، همیشه همین صفحه
        # (فرم تایید کد) نشان داده می‌شود تا وجود/عدم‌وجود شماره در سیستم لو نرود.
        if user:
            otp, raw_code, is_new = get_or_create_active_otp(phone_number, OTPCode.Purpose.PASSWORD_RESET, user=user)
            if is_new:
                error = _otp_ip_rate_limit_error(request)
                if error:
                    otp.delete()
                    return render(request, "accounts/partials/pwreset_phone_form.html", {
                        "error": error, "phone_number": phone_number,
                    })
                result = SMSService().send_otp(mobile=phone_number, code=raw_code)
                if not result.get("success"):
                    otp.delete()
                    return render(request, "accounts/partials/pwreset_phone_form.html", {
                        "error": "ارسال پیامک ناموفق بود، دوباره تلاش کنید.", "phone_number": phone_number,
                    })
            remaining = otp_remaining_seconds(phone_number, OTPCode.Purpose.PASSWORD_RESET)
            resent = not is_new

        return render(request, "accounts/partials/pwreset_verify_form.html", {
            "phone_number": phone_number, "remaining_seconds": remaining, "resent": resent,
        })

    return render(request, "accounts/password_reset_request.html")


def pwreset_phone_form(request):
    """برای دکمه‌ی «ویرایش شماره» در صفحه‌ی فراموشی رمز."""
    return render(request, "accounts/partials/pwreset_phone_form.html")


@require_POST
def verify_password_reset(request):
    phone_number = request.POST.get("phone_number", "").strip()
    code = request.POST.get("code", "").strip()
    new_password = request.POST.get("new_password", "").strip()
    new_password_confirm = request.POST.get("new_password_confirm", "").strip()

    common_ctx = {
        "phone_number": phone_number,
        "remaining_seconds": otp_remaining_seconds(phone_number, OTPCode.Purpose.PASSWORD_RESET),
    }

    if not new_password or not new_password_confirm:
        return render(request, "accounts/partials/pwreset_verify_form.html", {
            **common_ctx, "error": "لطفاً رمز عبور جدید و تکرار آن را وارد کنید.",
        })
    if new_password != new_password_confirm:
        return render(request, "accounts/partials/pwreset_verify_form.html", {
            **common_ctx, "error": "رمز عبور جدید و تکرار آن یکسان نیستند.",
        })

    ok, result = OTPCode.verify(phone_number, OTPCode.Purpose.PASSWORD_RESET, code)
    if not ok:
        return render(request, "accounts/partials/pwreset_verify_form.html", {**common_ctx, "error": result})

    user = User.objects.filter(phone_number=phone_number, is_active=True).first()
    if not user:
        return render(request, "accounts/partials/pwreset_verify_form.html", {
            **common_ctx, "error": "کاربری با این شماره یافت نشد.",
        })

    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return render(request, "accounts/partials/pwreset_verify_form.html", {
            **common_ctx, "error": " ".join(e.messages),
        })

    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    return HttpResponseClientRedirect(reverse("accounts:login"))


class StyledPasswordChangeView(PasswordChangeView):
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save(update_fields=["must_change_password"])
        return response
