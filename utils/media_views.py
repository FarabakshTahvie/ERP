import mimetypes
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header

from accounts.models import User
from core.capabilities import can


def _safe_path(rel):
    root = Path(settings.MEDIA_ROOT).resolve()
    full = (root / rel).resolve()
    if root not in full.parents or not full.is_file():
        raise Http404
    return full


def _allowed(user, rel):
    head = rel.split("/")[0]
    if head == "avatars":
        return True
    if head == "broadcast":
        return can(user, "broadcast.use")
    if head == "tasks":
        try:
            from tasks.models import TaskAttachment
            att = TaskAttachment.objects.filter(file=rel).select_related("task").first()
            return bool(att) and (att.task.created_by_id == user.id or att.task.assignments.filter(user=user).exists())
        except ImportError:
            return False
    if head == "payments":      # رسید: حسابدار/مدیر یا خود طرف‌حساب همان فاکتور
        from finance.models import Payment
        p = Payment.objects.filter(receipt_file=rel).select_related("invoice").first()
        if p is None:
            return False
        party = getattr(user, "party", None)
        return can(user, "accounting.access") or bool(party and p.invoice.billed_party_id == party.id)
    if head == "purchases":
        return can(user, "accounting.access") or can(user, "inventory.manage")
    if head == "projects":      # مشتری فقط از مسیر پرتال (portal_stage_file) فایل طرح می‌گیرد
        return user.is_superuser or user.role in (User.Role.ADMIN, User.Role.EMPLOYEE)
    if head == "messenger":
        from messenger.services import can_view_media
        return can_view_media(user, rel)
    return False


EXTRA_TYPES = {"m4a": "audio/mp4", "opus": "audio/ogg", "ogg": "audio/ogg", "mp3": "audio/mpeg",
               "aac": "audio/aac", "webm": "video/webm", "mov": "video/quicktime", "m4v": "video/mp4"}
_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def _content_type(path):
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return EXTRA_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def _is_inline(path):
    ctype = _content_type(path)
    return (ctype == "application/pdf" or ctype.startswith(("audio/", "video/"))
            or (ctype.startswith("image/") and ctype != "image/svg+xml"))


def _stream(path, start, length, chunk=64 * 1024):
    with open(path, "rb") as f:
        f.seek(start)
        left = length
        while left > 0:
            data = f.read(min(chunk, left))
            if not data:
                break
            left -= len(data)
            yield data


@login_required
def protected_media(request, path):
    if not _allowed(request.user, path):
        raise Http404
    full = _safe_path(path)
    size = full.stat().st_size
    start, end, status = 0, size - 1, 200
    m = _RANGE.match(request.headers.get("Range", "").strip())
    if m and (m.group(1) or m.group(2)) and size:
        if m.group(1):
            start = int(m.group(1))
            end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
        else:
            start = max(size - int(m.group(2)), 0)
        if start > end or start >= size:
            bad = HttpResponse(status=416)
            bad["Content-Range"] = f"bytes */{size}"
            return bad
        status = 206
    length = max(end - start + 1, 0)
    response = StreamingHttpResponse(_stream(full, start, length), status=status, content_type=_content_type(path))
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Content-Disposition"] = content_disposition_header(not _is_inline(path), full.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
