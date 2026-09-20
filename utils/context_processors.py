from django.conf import settings


def site_info(request):
    return {
        "CONTACT": settings.COMPANY_CONTACT,
        "NAJVA_ENABLED": settings.NAJVA_ENABLED,
    }
