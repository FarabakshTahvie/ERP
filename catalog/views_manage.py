from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.capabilities import cap_required
from utils.markdown_lite import render_markdown
from . import media as catalog_media
from .models import CatalogMedia


def _owner(kind, obj_id):
    obj = catalog_media.get_owner(kind, obj_id)
    if obj is None:
        raise Http404
    return obj


def _json(action):
    try:
        data = action()
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, **(data or {})})


@cap_required("catalog.edit")
def manage(request, kind, obj_id):
    obj = _owner(kind, obj_id)
    media = list(obj.media.all())
    _html, used = render_markdown(obj.description, catalog_media.media_map(obj))
    for m in media:
        m.in_text = m.pk in used
    return render(request, "catalog/manage.html", {
        "kind": kind, "obj": obj, "media": media,
        "upload_url": reverse("catalog:media_upload", args=[kind, obj.pk]),
        "cover_url": reverse("catalog:manage_cover", args=[kind, obj.pk]),
    })


@cap_required("catalog.edit")
@require_POST
def manage_save(request, kind, obj_id):
    _owner(kind, obj_id)
    try:
        catalog_media.update_content(kind=kind, obj_id=obj_id, show=request.POST.get("show_to_clients") == "on",
                                     description=request.POST.get("description", ""), actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "ذخیره شد.")
    return redirect("catalog:manage", kind, obj_id)


@cap_required("catalog.edit")
@require_POST
def manage_cover(request, kind, obj_id):
    _owner(kind, obj_id)
    if request.POST.get("remove") == "1":
        return _json(lambda: catalog_media.remove_cover(kind=kind, obj_id=obj_id, actor=request.user) and {})
    return _json(lambda: catalog_media.set_cover(kind=kind, obj_id=obj_id, uploaded=request.FILES.get("file"),
                                                 actor=request.user) and {})


@cap_required("catalog.edit")
@require_POST
def media_upload(request, kind, obj_id):
    _owner(kind, obj_id)

    def work():
        m = catalog_media.add_media(kind=kind, obj_id=obj_id, uploaded=request.FILES.get("file"), actor=request.user)
        return {"id": m.id, "name": m.original_name, "kind": m.kind}
    return _json(work)


@cap_required("catalog.edit")
@require_POST
def media_delete(request, media_id):
    media = get_object_or_404(CatalogMedia, pk=media_id)

    def work():
        catalog_media.delete_media(media=media, actor=request.user)
        return {}
    return _json(work)
