from django.conf import settings
from django.utils.functional import SimpleLazyObject

from core.capabilities import capabilities_for


def _unread_notifications_count(user):
    from datetime import timedelta
    from django.utils import timezone
    from notifications.models import Notification
    return Notification.objects.filter(user=user, seen_at__isnull=True,
                                       created_at__gte=timezone.now() - timedelta(days=30)).count()


def _pending_payments_count():
    from finance.models import Payment
    return Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY).count()


def _messenger_unread(user):
    from messenger.services import unread_total
    return unread_total(user)


def site_info(request):
    ctx = {
        "CONTACT": settings.COMPANY_CONTACT,
        "NAJVA_ENABLED": settings.NAJVA_ENABLED,
        "NESHAN_API_KEY": getattr(settings, "NESHAN_API_KEY", ""),
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        from utils.navigation import resolve_back
        ctx["back_url"] = resolve_back(request)
        caps = {name.replace(".", "_"): ok for name, ok in capabilities_for(user).items()}
        ctx["caps"] = caps                       # در تمپلیت: {% if caps.people_edit %}
        ctx["can_access_accounting"] = caps["accounting_access"]
        if caps["accounting_access"]:
            ctx["pending_payments_nav_count"] = SimpleLazyObject(_pending_payments_count)
        ctx["unread_notifications_count"] = SimpleLazyObject(lambda: _unread_notifications_count(user))
        if caps.get("messenger_use"):
            ctx["messenger_unread_count"] = SimpleLazyObject(lambda: _messenger_unread(user))
    return ctx
