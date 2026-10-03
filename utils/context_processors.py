from django.conf import settings
from django.utils.functional import SimpleLazyObject


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
        from projects.services import user_can_access_accounting
        allowed = user_can_access_accounting(user)
        ctx["can_access_accounting"] = allowed
        if allowed:
            ctx["pending_payments_nav_count"] = SimpleLazyObject(_pending_payments_count)
    return ctx
