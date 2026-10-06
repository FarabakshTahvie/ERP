import logging
import zlib

from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

EXEMPT_PREFIXES = ("/s/", "/manifest.json", "/najva-messaging-sw.js", "/utils/api/", "/static/", "/media/")
PRESENCE_SKIP_PREFIXES = ("/static/", "/media/", "/utils/", "/s/", "/manifest.json",
                          "/najva-messaging-sw.js", "/admin/jsi18n/")
PRESENCE_THROTTLE_SECONDS = 60


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            exempt = {reverse("accounts:force_set_password"), reverse("accounts:logout")}
            if request.path not in exempt and not request.path.startswith(EXEMPT_PREFIXES):
                return redirect(f"{reverse('accounts:force_set_password')}?next={request.path}")
        return self.get_response(request)


class PresenceMiddleware:
    """آخرین زمان و صفحه‌ی هر کاربر را ثبت می‌کند. فقط GET موفق، بدون htmx/ajax، حداکثر هر ۶۰ ثانیه برای هر صفحه."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._record(request, response)
        except Exception:   # ردپا هرگز نباید صفحه را خراب کند
            logger.exception("presence update failed")
        return response

    def _record(self, request, response):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return
        if request.method != "GET" or response.status_code != 200:
            return
        if request.headers.get("HX-Request") or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return
        path = request.path
        if path.startswith(PRESENCE_SKIP_PREFIXES):
            return
        key = f"presence:{user.pk}:{zlib.crc32(path.encode('utf-8'))}"
        if not cache.add(key, 1, PRESENCE_THROTTLE_SECONDS):
            return
        from .models import UserPresence
        match = getattr(request, "resolver_match", None)
        UserPresence.objects.update_or_create(user=user, defaults={
            "last_seen": timezone.now(), "last_path": path[:300],
            "view_name": (getattr(match, "view_name", "") or "")[:100],
        })
