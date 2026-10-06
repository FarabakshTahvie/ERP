import json
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Q

from core.capabilities import cap_required, can
from core.models import Specialty
from accounts.models import User
from utils.jalali import to_fa_digits, jalali_str
from utils.generic_table import build_table_context, render_table
from utils.models import PushDevice
from .models import Broadcast, Notification
from .broadcast import (
    resolve_audience,
    validate_link,
    calculate_digest,
    save_broadcast_asset,
    create_broadcast,
    retry_failed,
    parse_audience,
    parse_buttons,
    sms_parts,
    MAX_PUSH_RECIPIENTS,
    MAX_SMS_RECIPIENTS,
    AUDIENCE_FIELD,
    SIGNATURE,
)

PRESET_LINKS = [
    {"label": "صفحه اصلی", "url": "/"},
    {"label": "مرکز اعلان‌ها", "url": "/notifications/"},
    {"label": "صورت‌حساب من", "url": "/portal/statement/"},
]


def _render_form(request, values=None):
    push_enabled = bool(getattr(settings, "NAJVA_ENABLED", False) or getattr(settings, "BROADCAST_DRY_RUN", False))
    sms_enabled = bool(getattr(settings, "SMS_FREE_TEXT_ENABLED", False) or getattr(settings, "BROADCAST_DRY_RUN", False))
    specialties = Specialty.objects.all().order_by("name")

    return render(request, "notifications/broadcast_form.html", {
        "push_enabled": push_enabled,
        "sms_enabled": sms_enabled,
        "specialties": specialties,
        "preset_links": PRESET_LINKS,
        "is_admin": can(request.user, "admin.panel"),
        "max_push": MAX_PUSH_RECIPIENTS,
        "max_sms": MAX_SMS_RECIPIENTS,
        "values": values,
    })


@cap_required("broadcast.use")
def broadcast_form(request):
    """
    فرم ارسال پیام همگانی شامل تب‌های پوش و پیامک.
    """
    return _render_form(request)


def _draft(request):
    p = request.POST
    channel = p.get("channel")
    if channel not in ("push", "sms"):
        raise ValueError("کانال نامعتبر است.")
    try:
        ttl = int(p.get("ttl_hours") or 24)
    except ValueError:
        raise ValueError("مدت ماندگاری باید عدد باشد.")
    kind, ids = parse_audience(p)
    push = channel == "push"
    d = dict(
        channel=channel, title=(p.get("title") or "").strip() if push else "",
        body=(p.get("body") or "").strip(), link_path=(p.get("link_path") or "").strip(), ttl_hours=ttl,
        icon_name=(p.get("icon_name") or "").strip() if push else "",
        image_name=(p.get("image_name") or "").strip() if push else "",
        buttons=parse_buttons(p) if push else [], audience_kind=kind, audience_ids=ids)
    if push:
        for field, asset in (("icon_file", "icon"), ("image_file", "image")):
            if request.FILES.get(field):
                d[f"{asset}_name"] = save_broadcast_asset(request.FILES[field], kind=asset)
    from .broadcast import validate_content
    validate_content(channel, d["title"], d["body"], ttl, d["image_name"], d["icon_name"], d["buttons"])
    if d["link_path"] and not validate_link(d["link_path"]):
        raise ValueError("لینک نامعتبر یا خارجی است.")
    return d


def _hidden_fields(d):
    out = [(k, d[k]) for k in ("channel", "title", "body", "link_path", "ttl_hours", "icon_name", "image_name", "audience_kind")]
    if d["audience_kind"] != "all_staff":
        out += [(AUDIENCE_FIELD[d["audience_kind"]], i) for i in d["audience_ids"]]
    for n, b in enumerate(d["buttons"], 1):
        out += [(f"btn{n}_title", b["title"]), (f"btn{n}_path", b["path"])]
    return out


@cap_required("broadcast.use")
def broadcast_preview(request):
    """
    پیش‌نمایش پیام همگانی، اعتبارسنجی اولیه، محاسبه digest و تایید نهایی.
    """
    if request.method != "POST":
        return redirect("notifications:broadcast_form")
    action = request.POST.get("action", "preview")
    try:
        d = _draft(request)
        if action == "test_self":
            b = create_broadcast(
                channel=d["channel"], title=d["title"], body=d["body"],
                link_path=d["link_path"], icon_name=d["icon_name"], image_name=d["image_name"],
                ttl_hours=d["ttl_hours"], audience_kind=d["audience_kind"], audience_ids=d["audience_ids"],
                created_by=request.user, buttons=d["buttons"], is_test=True
            )
            messages.success(request, "ارسال آزمایشی در صف قرار گرفت.")
            return redirect("notifications:broadcast_detail", broadcast_id=b.id)
        
        users = resolve_audience(d["audience_kind"], d["audience_ids"], d["channel"])
        if not users:
            raise ValueError("گیرنده‌ای پیدا نشد.")
        
        if action == "confirm_send":
            b = create_broadcast(
                channel=d["channel"], title=d["title"], body=d["body"],
                link_path=d["link_path"], icon_name=d["icon_name"], image_name=d["image_name"],
                ttl_hours=d["ttl_hours"], audience_kind=d["audience_kind"], audience_ids=d["audience_ids"],
                created_by=request.user, buttons=d["buttons"], digest=request.POST.get("digest")
            )
            messages.success(request, "پیام در صف ارسال قرار گرفت.")
            return redirect("notifications:broadcast_detail", broadcast_id=b.id)
        
        digest = calculate_digest(
            channel=d["channel"], title=d["title"], body=d["body"],
            link_path=d["link_path"], ttl_hours=d["ttl_hours"], icon_name=d["icon_name"],
            image_name=d["image_name"], buttons=d["buttons"], audience_kind=d["audience_kind"],
            audience_ids=d["audience_ids"], resolved_user_ids=[u.id for u in users]
        )
    except ValueError as e:
        messages.error(request, str(e))
        return _render_form(request, values=request.POST)

    # Estimate stats
    full_audience = resolve_audience(d["audience_kind"], d["audience_ids"], "push")
    skipped_count = len(full_audience) - len(users) if d["channel"] == "sms" else 0

    no_device_count = 0
    if d["channel"] == "push":
        active_device_user_ids = set(PushDevice.objects.filter(user__in=users, is_active=True).values_list("user_id", flat=True))
        no_device_count = sum(1 for u in users if u.id not in active_device_user_ids)

    # Estimate SMS length and parts
    final_text_len = len(d["body"]) + len("\n" + SIGNATURE)
    if d["link_path"]:
        final_text_len += 1 + len(settings.SITE_BASE_URL.rstrip('/')) + 8 # plus a newline and tracking url
    estimated_parts = sms_parts(final_text_len)

    return render(request, "notifications/broadcast_preview.html", {
        **d,
        "hidden": _hidden_fields(d),
        "digest": digest,
        "recipients_count": len(users),
        "skipped_count": skipped_count,
        "no_device_count": no_device_count,
        "sms_parts": estimated_parts,
        "signature": SIGNATURE,
        "site_base_url": settings.SITE_BASE_URL,
    })


def _build_history_table_context(request):
    qs = Broadcast.objects.select_related("created_by").annotate(
        sent_c=Count("notifications", filter=Q(notifications__status__in=[
            Notification.Status.PUSH_SENT, Notification.Status.SMS_SENT, Notification.Status.SEEN
        ]), distinct=True),
        seen_c=Count("notifications", filter=Q(notifications__seen_at__isnull=False), distinct=True),
        clicked_c=Count("notifications", filter=Q(notifications__click_events__isnull=False), distinct=True),
        failed_c=Count("notifications", filter=Q(notifications__status=Notification.Status.FAILED), distinct=True),
    ).order_by("-created_at")

    def row_builder(b):
        if b.channel == "push":
            channel_val = "پوش" + (" (آزمایشی)" if b.is_test else "")
            channel_variant = "info"
        else:
            channel_val = "پیامک" + (" (آزمایشی)" if b.is_test else "")
            channel_variant = "accent"

        return {
            "url": reverse("notifications:broadcast_detail", args=[b.id]),
            "cells": [
                {"type": "text", "value": jalali_str(b.created_at, fmt="%Y/%m/%d %H:%M")},
                {"type": "text", "value": b.created_by.get_full_name() or b.created_by.username if b.created_by else "-"},
                {"type": "badge", "value": channel_val, "variant": channel_variant},
                {"type": "text", "value": b.title or b.body[:30]},
                {"type": "text", "value": to_fa_digits(b.recipients_count)},
                {"type": "text", "value": to_fa_digits(b.sent_c)},
                {"type": "text", "value": to_fa_digits(b.seen_c)},
                {"type": "text", "value": to_fa_digits(b.clicked_c)},
                {"type": "text", "value": to_fa_digits(b.failed_c)},
            ]
        }

    return build_table_context(
        request, qs,
        columns=[
            {"label": "زمان", "sort_field": "created_at"},
            {"label": "فرستنده"},
            {"label": "کانال"},
            {"label": "عنوان / خلاصه"},
            {"label": "گیرندگان", "sort_field": "recipients_count"},
            {"label": "ارسال‌شده"},
            {"label": "دیده‌شده"},
            {"label": "کلیک‌شده"},
            {"label": "ناموفق"},
        ],
        row_builder=row_builder,
        container_id="table-broadcast-history",
        param_prefix="bh_",
        empty_icon="send",
        empty_text="هیچ پیام همگانی ارسال نشده است.",
        list_url=reverse("notifications:broadcast_history_table"),
        search_fields=["title", "body", "audience_label"],
        search_placeholder="جستجو در عنوان یا متن پیام...",
    )


@cap_required("broadcast.use")
def broadcast_history(request):
    """
    فهرست ارسال‌ها و آمار کلی با جدول ژنریک (پیشوند bh_).
    """
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # کارت‌های آمار این ماه (به جز ارسال‌های آزمایشی)
    monthly_broadcasts = Broadcast.objects.filter(created_at__gte=start_of_month, is_test=False)
    total_broadcasts = monthly_broadcasts.count()
    total_recipients = sum(monthly_broadcasts.values_list("recipients_count", flat=True)) or 0

    monthly_notifs = Notification.objects.filter(broadcast__in=monthly_broadcasts)
    seen_count = monthly_notifs.filter(seen_at__isnull=False).count()
    clicked_count = monthly_notifs.filter(click_events__isnull=False).distinct().count()

    seen_rate = round((seen_count / total_recipients * 100), 1) if total_recipients > 0 else 0
    click_rate = round((clicked_count / total_recipients * 100), 1) if total_recipients > 0 else 0

    table_ctx = _build_history_table_context(request)
    ctx = {
        "stats": {
            "total_broadcasts": total_broadcasts,
            "total_recipients": total_recipients,
            "seen_rate": to_fa_digits(f"{seen_rate}٪"),
            "click_rate": to_fa_digits(f"{click_rate}٪"),
        }
    }
    ctx.update(table_ctx)
    return render(request, "notifications/broadcast_history.html", ctx)


@cap_required("broadcast.use")
def broadcast_history_table(request):
    table_ctx = _build_history_table_context(request)
    return render_table(request, table_ctx)


def _build_detail_table_context(request, broadcast_id):
    broadcast = get_object_or_404(Broadcast, pk=broadcast_id)
    notifs = broadcast.notifications.select_related("user").annotate(
        clicks_count=Count("click_events", distinct=True)
    ).all()

    def row_builder(n):
        status_map = {
            Notification.Status.PENDING: ("در صف", "warning"),
            Notification.Status.PUSH_SENT: ("پوش فرستاده شد", "success"),
            Notification.Status.SMS_SENT: ("پیامک فرستاده شد", "success"),
            Notification.Status.IN_APP: ("فقط داخل برنامه", "info"),
            Notification.Status.SEEN: ("دیده شد", "primary"),
            Notification.Status.FAILED: ("ناموفق", "error"),
        }
        status_lbl, variant = status_map.get(n.status, (n.status, "neutral"))
        seen_time = jalali_str(n.seen_at, fmt="%Y/%m/%d %H:%M") if n.seen_at else "-"

        return {
            "cells": [
                {"type": "text", "value": n.user.get_full_name() or n.user.username},
                {"type": "badge", "value": status_lbl, "variant": variant},
                {"type": "text", "value": seen_time},
                {"type": "text", "value": to_fa_digits(n.clicks_count)},
                {"type": "text", "value": n.error_text or "-"},
            ]
        }

    return build_table_context(
        request, notifs,
        columns=[
            {"label": "گیرنده"},
            {"label": "وضعیت"},
            {"label": "زمان دیده‌شدن"},
            {"label": "تعداد کلیک"},
            {"label": "خطا"},
        ],
        row_builder=row_builder,
        container_id="table-broadcast-recipients",
        param_prefix="bd_",
        empty_icon="users",
        empty_text="گیرنده‌ای یافت نشد.",
        list_url=reverse("notifications:broadcast_detail_table", args=[broadcast_id]),
        search_fields=["user__first_name", "user__last_name", "user__username", "user__phone_number"],
        search_placeholder="جستجو در نام، نام کاربری یا شماره...",
    )


@cap_required("broadcast.use")
def broadcast_detail(request, broadcast_id):
    """
    صفحه جزئیات پیام همگانی و جدول وضعیت گیرندگان (پیشوند bd_).
    """
    broadcast = get_object_or_404(Broadcast.objects.select_related("created_by"), pk=broadcast_id)
    notifs = broadcast.notifications.select_related("user").all()

    recipients_count = broadcast.recipients_count
    sent_count = notifs.filter(status__in=[Notification.Status.PUSH_SENT, Notification.Status.SMS_SENT, Notification.Status.SEEN]).count()
    in_app_count = notifs.filter(status=Notification.Status.IN_APP).count()
    failed_count = notifs.filter(status=Notification.Status.FAILED).count()
    seen_count = notifs.filter(seen_at__isnull=False).count()
    clicked_count = notifs.filter(click_events__isnull=False).distinct().count()
    click_rate = round((clicked_count / recipients_count * 100), 1) if recipients_count > 0 else 0

    table_ctx = _build_detail_table_context(request, broadcast_id)
    ctx = {
        "broadcast": broadcast,
        "stats": {
            "recipients_count": recipients_count,
            "sent_count": sent_count,
            "in_app_count": in_app_count,
            "failed_count": failed_count,
            "seen_count": seen_count,
            "clicked_count": clicked_count,
            "click_rate": to_fa_digits(f"{click_rate}٪"),
        }
    }
    ctx.update(table_ctx)
    return render(request, "notifications/broadcast_detail.html", ctx)


@cap_required("broadcast.use")
def broadcast_detail_table(request, broadcast_id):
    table_ctx = _build_detail_table_context(request, broadcast_id)
    return render_table(request, table_ctx)


@cap_required("broadcast.use")
@require_POST
def broadcast_retry(request, broadcast_id):
    """
    ارسال دوباره برای گیرندگان با وضعیت ناموفق (FAILED).
    """
    broadcast = get_object_or_404(Broadcast, pk=broadcast_id)
    count = retry_failed(broadcast)
    messages.success(request, f"{to_fa_digits(count)} پیام ناموفق مجدداً در صف ارسال قرار گرفتند.")
    return redirect("notifications:broadcast_detail", broadcast_id=broadcast.id)
