from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import LoginHistory
from utils.request_meta import get_client_ip, parse_user_agent


@receiver(user_logged_in)
def on_login_success(sender, request, user, **kwargs):
    if not request:
        return
    ua = parse_user_agent(request)
    LoginHistory.objects.create(
        user=user, username_attempted=user.username, result=LoginHistory.Result.SUCCESS,
        ip_address=get_client_ip(request), user_agent=ua["raw"],
        browser=ua["browser"], os=ua["os"], device_type=ua["device_type"],
    )
    request.session["user_avatar_url"] = user.avatar.url if user.avatar else None


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    if not request:
        return
    ua = parse_user_agent(request)
    LoginHistory.objects.create(
        user=None, username_attempted=credentials.get("username", ""), result=LoginHistory.Result.FAILED,
        ip_address=get_client_ip(request), user_agent=ua["raw"],
        browser=ua["browser"], os=ua["os"], device_type=ua["device_type"],
    )
