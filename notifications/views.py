from django.http import HttpResponseRedirect, Http404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from utils.request_meta import get_client_ip
from .models import Notification, NotificationClickEvent

BOT_MARKERS = ("bot", "crawler", "spider", "preview", "facebookexternalhit",
               "whatsapp", "telegram", "slack", "curl", "python-requests", "headless")


def _is_bot(request):
    """پیش‌نمایش لینک در آیفون/تلگرام/واتساپ نباید «باز شدن» حساب شود."""
    if request.method != "GET":
        return True
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    return not ua or any(m in ua for m in BOT_MARKERS)


def track_and_redirect(request, code):
    notification = Notification.objects.filter(short_code=code).first()
    if not notification:
        raise Http404
    if not _is_bot(request):
        channel = request.GET.get("ch")
        NotificationClickEvent.objects.create(
            notification=notification,
            channel=channel if channel in ("push", "sms") else "sms",
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
        # اتمیک: فقط اولین کلیک «دیده‌شده» را ثبت می‌کند
        Notification.objects.filter(pk=notification.pk, seen_at__isnull=True).update(
            seen_at=timezone.now(), status=Notification.Status.SEEN)

    target = notification.real_target_url or "/"
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = "/"
    return HttpResponseRedirect(target)
