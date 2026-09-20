from django.shortcuts import redirect
from django.urls import reverse


EXEMPT_PREFIXES = ("/s/", "/manifest.json", "/najva-messaging-sw.js", "/utils/api/", "/static/", "/media/")


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            exempt = {reverse("accounts:change_password"), reverse("accounts:logout")}
            if request.path not in exempt and not request.path.startswith(EXEMPT_PREFIXES):
                return redirect("accounts:change_password")
        return self.get_response(request)
