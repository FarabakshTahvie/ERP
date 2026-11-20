import re

from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST, require_safe

from core.capabilities import can, cap_required
from utils.media_views import _content_type, _is_inline
from . import services, storage
from .models import ManagedFile

LIST_LIMIT = 300
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _run(work):
    try:
        work()
    except ValueError as e:   # StorageError هم ValueError است
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})


@cap_required("files.manage")
def file_list(request):
    total = ManagedFile.objects.count()
    files = list(ManagedFile.objects.select_related("uploaded_by")[:LIST_LIMIT])
    for f in files:
        f.short_url = request.build_absolute_uri(reverse("filemanager:open", args=[f.code]))
        f.size_text = services.size_text(f.size)
        f.icon = services.icon_for(f.name)
    used = services.used_bytes()
    return render(request, "filemanager/list.html", {
        "files": files, "total_count": total, "list_limit": LIST_LIMIT,
        "used_text": services.size_text(used), "limit_text": services.size_text(services.TOTAL_LIMIT_BYTES),
        "percent": min(100, int(used * 100 / services.TOTAL_LIMIT_BYTES)),
        "max_text": services.size_text(services.MAX_FILE_BYTES),
        "upload_url": reverse("filemanager:upload"), "storage_ready": storage.configured(),
    })


@cap_required("files.manage")
@require_POST
def file_upload(request):
    return _run(lambda: services.upload_file(actor=request.user, uploaded=request.FILES.get("file")))


@cap_required("files.manage")
@require_POST
def file_visibility(request, pk):
    return _run(lambda: services.set_public(actor=request.user, file_id=pk,
                                            public=request.POST.get("public") == "1"))


@cap_required("files.manage")
@require_POST
def file_delete(request, pk):
    return _run(lambda: services.delete_file(actor=request.user, file_id=pk))


def _chunks(body):
    try:
        yield from body.iter_chunks(64 * 1024)
    finally:
        body.close()


@require_safe
def file_open(request, code):
    """لینک کوتاه. عمومی: بدون ورود. خصوصی: فقط مدیر و حسابدار (ناوارد ← صفحه‌ی ورود، بدون قابلیت ← ۴۰۴)."""
    f = get_object_or_404(ManagedFile, code=code)
    if not f.is_public:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can(request.user, "files.manage"):
            raise Http404
    raw = request.headers.get("Range", "").strip()
    m = _RANGE.match(raw)
    byte_range = raw if (m and (m.group(1) or m.group(2))) else None
    try:
        obj = storage.open_object(f.key, byte_range)
    except storage.ObjectMissing:
        raise Http404
    except storage.RangeNotSatisfiable:
        bad = HttpResponse(status=416)
        bad["Content-Range"] = f"bytes */{f.size}"
        return bad
    except storage.StorageError as e:
        return HttpResponse(str(e), status=503, content_type="text/plain; charset=utf-8")

    status = 206 if obj.get("ContentRange") else 200
    response = StreamingHttpResponse(_chunks(obj["Body"]), status=status, content_type=_content_type(f.name))
    response["Content-Length"] = str(obj["ContentLength"])
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = obj["ContentRange"]
    inline = _is_inline(f.name) and request.GET.get("dl") != "1"
    response["Content-Disposition"] = content_disposition_header(not inline, f.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = "public, max-age=60" if f.is_public else "private, no-store"
    return response
