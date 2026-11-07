from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.capabilities import can, is_manager
from .models import ProjectStage, StageKind, StageUsage
from .ops import can_edit_ops
from .services import resolve_billing_party

BLANK = "---"
_SHOWN = (ProjectStage.Status.IN_PROGRESS, ProjectStage.Status.DONE)


def can_view_slip(user, stage):
    """برگه‌ی ارسال: مسئول مرحله، ثبت‌کننده و مدیر (can_edit_ops) و مدیر یا حسابدار (accounting.access)."""
    if stage.kind != StageKind.SHIPPING or stage.status not in _SHOWN:
        return False
    return bool(user.is_authenticated and (
        stage.assigned_to_id == user.id or can_edit_ops(user, stage) or can(user, "accounting.access")))


def tracks_download(user, stage):
    """دانلود فقط وقتی ثبت می‌شود که مرحله در حال انجام است و دانلودکننده کسی است که می‌تواند تکمیلش کند."""
    return stage.status == ProjectStage.Status.IN_PROGRESS and (
        stage.assigned_to_id == user.id or is_manager(user))


def mark_downloaded(stage, user):
    if tracks_download(user, stage):
        ProjectStage.objects.filter(pk=stage.pk, status=ProjectStage.Status.IN_PROGRESS).update(
            slip_downloaded_at=timezone.now())


def slip_data(stage):
    """تنها منبع محتوای برگه (PDF، مودال و صفحه‌ی مشتری). فقط اقلام ثبت‌شده در همین مرحله."""
    project = stage.project
    party = resolve_billing_party(project)
    location = project.location
    address = (location.address_text or "").strip() if location else ""
    coords = f"{location.latitude}, {location.longitude}" if location and location.has_exact_coordinates else ""
    rows = [{"name": u.item.name, "qty": u.qty, "unit": u.item.get_unit_display()}
            for u in StageUsage.objects.filter(stage=stage).select_related("item").order_by("item__name", "pk")]
    return {"party_name": party.name if party else BLANK, "project_code": project.code,
            "address": address or BLANK, "location": coords or BLANK, "rows": rows}


def stage_context(user, stage):
    """برای نمای پروژه؛ None یعنی این کاربر برگه نمی‌بیند."""
    if not can_view_slip(user, stage):
        return None
    ctx = slip_data(stage)
    ctx.update(pdf_url=reverse("projects:shipping_slip_pdf", args=[stage.id]),
               can_preview=can(user, "accounting.access"),
               tracks=tracks_download(user, stage),
               downloaded_at=stage.slip_downloaded_at)
    return ctx


def render_pdf(request, stage):
    import weasyprint
    html = render_to_string("projects/shipping_slip_pdf.html", {"slip": slip_data(stage)})
    return weasyprint.HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
