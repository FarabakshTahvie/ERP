import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404

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
    return False


def _is_inline(path):
    ctype, _ = mimetypes.guess_type(path)
    return bool(ctype) and (ctype == "application/pdf" or (ctype.startswith("image/") and ctype != "image/svg+xml"))


@login_required
def protected_media(request, path):
    if not _allowed(request.user, path):
        raise Http404
    full = _safe_path(path)
    response = FileResponse(open(full, "rb"), as_attachment=not _is_inline(path), filename=full.name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
