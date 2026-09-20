from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            exempt = {reverse("accounts:change_password"), reverse("accounts:logout")}
            if request.path not in exempt and not (
                request.path.startswith("/s/") or
                request.path.startswith("/manifest.json") or
                request.path.startswith("/utils/api/")
            ):
                return redirect("accounts:change_password")
        return self.get_response(request)
