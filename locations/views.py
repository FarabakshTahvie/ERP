from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.capabilities import cap_required
from . import services
from .models import SavedLocation


def _run(work):
    try:
        work()
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})


def _fields(request):
    p = request.POST
    return dict(title=p.get("title"), description=p.get("description"), lat_raw=p.get("latitude"),
                lng_raw=p.get("longitude"), image=request.FILES.get("image"))


@cap_required("locations.manage")
def location_list(request):
    places = list(SavedLocation.objects.all())
    for p in places:
        p.public_url = request.build_absolute_uri(reverse("locations:public", kwargs={"token": p.token}))
    return render(request, "locations/list.html", {"places": places})


@cap_required("locations.manage")
@require_POST
def location_create(request):
    return _run(lambda: services.create_location(actor=request.user, **_fields(request)))


@cap_required("locations.manage")
@require_POST
def location_update(request, pk):
    return _run(lambda: services.update_location(
        actor=request.user, location_id=pk, remove_image=request.POST.get("remove_image") == "1",
        **_fields(request)))


@cap_required("locations.manage")
@require_POST
def location_delete(request, pk):
    return _run(lambda: services.delete_location(actor=request.user, location_id=pk))


def public_location(request, token):
    """صفحه‌ی عمومی؛ بدون ورود. دسترسی فقط با کد حدس‌نزدنی (۳۲ نویسه‌ی هگز)."""
    place = get_object_or_404(SavedLocation, token=token)
    response = render(request, "locations/public.html", {
        "place": place,
        "image_url": reverse("locations:public_image", kwargs={"token": token}) if place.image else ""})
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


def public_location_image(request, token):
    place = get_object_or_404(SavedLocation, token=token)
    if not place.image:
        raise Http404
    try:
        handle = place.image.open("rb")
    except OSError:
        raise Http404
    response = FileResponse(handle, as_attachment=False)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=300"
    return response
