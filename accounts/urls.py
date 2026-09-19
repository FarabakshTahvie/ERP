from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

app_name = "accounts"
urlpatterns = [
    path("login/", views.StyledLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("login/otp/request/", views.request_otp_login, name="request_otp_login"),
    path("login/otp/verify/", views.verify_otp_login, name="verify_otp_login"),
    path("register-staff/", views.register_staff, name="register_staff"),
    path("password-reset/", views.request_password_reset, name="password_reset_request"),
    path("password-reset/verify/", views.verify_password_reset, name="password_reset_verify"),
    path("change-password/", views.StyledPasswordChangeView.as_view(), name="change_password"),
]
