from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.capabilities import can, is_manager
from utils.jalali import jalali_str
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


def mark_downloaded(stage, user, when=None):
    if tracks_download(user, stage):
        ProjectStage.objects.filter(pk=stage.pk, status=ProjectStage.Status.IN_PROGRESS).update(
            slip_downloaded_at=when or timezone.now())


def slip_date(stage, when=None):
    """تاریخ برگه: لحظه‌ی همین دانلود (when)، وگرنه آخرین دانلود تکنسین، وگرنه زمان تکمیل مرحله، وگرنه الان."""
    value = when or stage.slip_downloaded_at or stage.completed_at or timezone.now()
    return jalali_str(value, fmt="%Y/%m/%d")


def slip_data(stage, when=None):
    """تنها منبع محتوای برگه (PDF، مودال و صفحه‌ی مشتری). فقط اقلام ثبت‌شده در همین مرحله."""
    project = stage.project
    party = resolve_billing_party(project)
    location = project.location
    address = (location.address_text or "").strip() if location else ""
    rows = [{"name": u.item.name, "qty": u.qty, "unit": u.item.get_unit_display()}
            for u in StageUsage.objects.filter(stage=stage).select_related("item").order_by("item__name", "pk")]
    return {"party_name": party.name if party else BLANK, "project_code": project.code,
            "address": address or BLANK, "rows": rows, "date": slip_date(stage, when)}


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


def render_pdf(request, stage, when=None):
    import weasyprint
    html = render_to_string("projects/shipping_slip_pdf.html", {"slip": slip_data(stage, when)})
    return weasyprint.HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
