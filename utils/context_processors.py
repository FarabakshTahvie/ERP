from django.conf import settings
from django.utils.functional import SimpleLazyObject

from core.capabilities import capabilities_for


def _pending_payments_count():
    from finance.models import Payment
    return Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY).count()


def site_info(request):
    ctx = {
        "CONTACT": settings.COMPANY_CONTACT,
        "NAJVA_ENABLED": settings.NAJVA_ENABLED,
        "NESHAN_API_KEY": getattr(settings, "NESHAN_API_KEY", ""),
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        caps = {name.replace(".", "_"): ok for name, ok in capabilities_for(user).items()}
        ctx["caps"] = caps                       # در تمپلیت: {% if caps.people_edit %}
        ctx["can_access_accounting"] = caps["accounting_access"]
        if caps["accounting_access"]:
            ctx["pending_payments_nav_count"] = SimpleLazyObject(_pending_payments_count)
    return ctx
