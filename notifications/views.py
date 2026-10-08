from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
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


@login_required
def center(request):
    from utils.models import PushDevice
    items = list(Notification.objects.filter(user=request.user).order_by("-created_at")[:50])
    return render(request, "notifications/center.html", {
        "items": items,
        "push_devices": PushDevice.objects.filter(user=request.user, is_active=True).count(),
    })


@login_required
@require_POST
def mark_all_seen(request):
    """«دیده شد» داخل برنامه، پیامک جایگزین را هم لغو می‌کند (cron فقط PUSH_SENT دیده‌نشده را می‌فرستد)."""
    now = timezone.now()
    qs = Notification.objects.filter(user=request.user, seen_at__isnull=True)
    qs.filter(status__in=[Notification.Status.PENDING, Notification.Status.PUSH_SENT,
                          Notification.Status.IN_APP]).update(seen_at=now, status=Notification.Status.SEEN)
    qs.update(seen_at=now)
    return redirect("notifications:center")
