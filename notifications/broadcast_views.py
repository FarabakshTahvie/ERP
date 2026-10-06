import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect, Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count, Q

from core.capabilities import cap_required, can
from core.models import Specialty
from accounts.models import User
from utils.jalali import to_fa_digits
from utils.generic_table import build_table_context, render_table
from .models import Broadcast, Notification, NotificationClickEvent
from .broadcast import (
    resolve_audience,
    validate_link,
    calculate_digest,
    save_broadcast_asset,
    create_broadcast,
    retry_failed,
    MAX_PUSH_RECIPIENTS,
    MAX_SMS_RECIPIENTS,
)

PRESET_LINKS = [
    {"label": "صفحه اصلی", "url": "/"},
    {"label": "مرکز اعلان‌ها", "url": "/notifications/"},
    {"label": "صورت‌حساب من", "url": "/accounts/invoices/"},
]


@cap_required("broadcast.use")
def broadcast_form(request):
    """
    فرم ارسال پیام همگانی شامل تب‌های پوش و پیامک.
    """
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
    })


@cap_required("broadcast.use")
def broadcast_preview(request):
    """
    پیش‌نمایش پیام همگانی، اعتبارسنجی اولیه، محاسبه digest و تایید نهایی.
    """
    if request.method == "POST":
        action = request.POST.get("action", "preview")  # preview | send | test_self
        channel = request.POST.get("channel", "push")
        title = request.POST.get("title", "").strip()
        body = request.POST.get("body", "").strip()
        link_path = request.POST.get("link_path", "").strip()
        ttl_hours = int(request.POST.get("ttl_hours") or 24)
        audience_kind = request.POST.get("audience_kind", "all_staff")
        audience_ids = request.POST.getlist("audience_ids")
        if audience_ids:
            try:
                audience_ids = [int(i) for i in audience_ids if str(i).isdigit()]
            except ValueError:
                audience_ids = []

        icon_name = request.POST.get("icon_name", "").strip()
        image_name = request.POST.get("image_name", "").strip()

        # بررسی آپلود تصویر جدید
        if "image_file" in request.FILES:
            try:
                image_name = save_broadcast_asset(request.FILES["image_file"], kind="image")
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("notifications:broadcast_form")

        # اعتبارسنجی لینک
        if link_path and not validate_link(link_path):
            messages.error(request, "لینک وارد شده نامعتبر یا خارجی است.")
            return redirect("notifications:broadcast_form")

        digest = calculate_digest(body, audience_kind, audience_ids, image_name, channel)

        # ارسال آزمایشی به خود
        if action == "test_self":
            try:
                broadcast = create_broadcast(
                    channel=channel,
                    title=title,
                    body=body,
                    link_path=link_path,
                    icon_name=icon_name,
                    image_name=image_name,
                    ttl_hours=ttl_hours,
                    audience_kind=audience_kind,
                    audience_ids=audience_ids,
                    audience_label="آزمایشی به فرستنده",
                    created_by=request.user,
                    is_test=True,
                    digest=digest,
                )
                messages.success(request, "ارسال آزمایشی با موفقیت ثبت شد.")
                return redirect("notifications:broadcast_detail", broadcast_id=broadcast.id)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("notifications:broadcast_form")

        # تایید نهایی و صدور
        if action == "confirm_send":
            submitted_digest = request.POST.get("digest")
            try:
                broadcast = create_broadcast(
                    channel=channel,
                    title=title,
                    body=body,
                    link_path=link_path,
                    icon_name=icon_name,
                    image_name=image_name,
                    ttl_hours=ttl_hours,
                    audience_kind=audience_kind,
                    audience_ids=audience_ids,
                    audience_label=request.POST.get("audience_label", ""),
                    created_by=request.user,
                    is_test=False,
                    digest=submitted_digest,
                )
                messages.success(request, "پیام همگانی در صف ارسال قرار گرفت.")
                return redirect("notifications:broadcast_detail", broadcast_id=broadcast.id)
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("notifications:broadcast_form")

        # حالت نمایش پیش‌نمایش (action == 'preview')
        audience_users = resolve_audience(audience_kind, audience_ids, channel)
        full_audience = resolve_audience(audience_kind, audience_ids, "push")
        skipped_count = len(full_audience) - len(audience_users) if channel == "sms" else 0

        # محاسبه برآورد بخش‌های پیامک (هر بخش پیامک فارسی حدود ۷۰ کاراکتر است)
        sms_parts = 1
        if channel == "sms":
            total_sms_length = len(body) + (len(link_path) + 30 if link_path else 0) + 15
            sms_parts = max(1, (total_sms_length + 66) // 67)

        return render(request, "notifications/broadcast_preview.html", {
            "channel": channel,
            "title": title,
            "body": body,
            "link_path": link_path,
            "ttl_hours": ttl_hours,
            "audience_kind": audience_kind,
            "audience_ids": json.dumps(audience_ids),
            "audience_label": f"{len(audience_users)} گیرنده",
            "recipients_count": len(audience_users),
            "skipped_count": skipped_count,
            "sms_parts": sms_parts,
            "icon_name": icon_name,
            "image_name": image_name,
            "digest": digest,
        })

    return redirect("notifications:broadcast_form")


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

    qs = Broadcast.objects.select_related("created_by").all().order_by("-created_at")

    def row_builder(b):
        sent_c = b.notifications.filter(status__in=[Notification.Status.PUSH_SENT, Notification.Status.SMS_SENT, Notification.Status.SEEN]).count()
        seen_c = b.notifications.filter(seen_at__isnull=False).count()
        clicked_c = b.notifications.filter(click_events__isnull=False).distinct().count()
        failed_c = b.notifications.filter(status=Notification.Status.FAILED).count()

        channel_badge = (
            f'<span class="badge badge-info badge-sm">پوش</span>'
            if b.channel == "push"
            else f'<span class="badge badge-accent badge-sm">پیامک</span>'
        )
        if b.is_test:
            channel_badge += ' <span class="badge badge-warning badge-sm">آزمایشی</span>'

        title_display = f'<a href="{reverse("notifications:broadcast_detail", args=[b.id])}" class="link link-hover font-semibold">{b.title or b.body[:30]}</a>'

        return {
            "id": b.id,
            "cells": [
                {"type": "text", "value": to_fa_digits(b.created_at.strftime("%Y/%m/%d %H:%M"))},
                {"type": "text", "value": b.created_by.get_full_name() or b.created_by.username if b.created_by else "-"},
                {"type": "html", "value": channel_badge},
                {"type": "html", "value": title_display},
                {"type": "text", "value": to_fa_digits(b.recipients_count)},
                {"type": "text", "value": to_fa_digits(sent_c)},
                {"type": "text", "value": to_fa_digits(seen_c)},
                {"type": "text", "value": to_fa_digits(clicked_c)},
                {"type": "text", "value": to_fa_digits(failed_c)},
            ]
        }

    table_ctx = build_table_context(
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
        list_url=reverse("notifications:broadcast_history"),
        search_fields=["title", "body", "audience_label"],
        search_placeholder="جستجو در عنوان یا متن پیام...",
    )

    if request.headers.get("HX-Request"):
        return render_table(request, table_ctx)

    return render(request, "notifications/broadcast_history.html", {
        "table": table_ctx,
        "stats": {
            "total_broadcasts": total_broadcasts,
            "total_recipients": total_recipients,
            "seen_rate": seen_rate,
            "click_rate": click_rate,
        }
    })


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

    def row_builder(n):
        status_map = {
            Notification.Status.PENDING: '<span class="badge badge-warning badge-sm">در صف</span>',
            Notification.Status.PUSH_SENT: '<span class="badge badge-success badge-sm">پوش فرستاده شد</span>',
            Notification.Status.SMS_SENT: '<span class="badge badge-success badge-sm">پیامک فرستاده شد</span>',
            Notification.Status.IN_APP: '<span class="badge badge-info badge-sm">فقط داخل برنامه</span>',
            Notification.Status.SEEN: '<span class="badge badge-primary badge-sm">دیده شد</span>',
            Notification.Status.FAILED: '<span class="badge badge-error badge-sm">ناموفق</span>',
        }
        badge = status_map.get(n.status, n.status)
        seen_time = to_fa_digits(n.seen_at.strftime("%Y/%m/%d %H:%M")) if n.seen_at else "-"
        clicks = n.click_events.count()

        return {
            "id": n.id,
            "cells": [
                {"type": "text", "value": n.user.get_full_name() or n.user.username},
                {"type": "html", "value": badge},
                {"type": "text", "value": seen_time},
                {"type": "text", "value": to_fa_digits(clicks)},
                {"type": "text", "value": n.error_text or "-"},
            ]
        }

    table_ctx = build_table_context(
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
        list_url=reverse("notifications:broadcast_detail", args=[broadcast.id]),
        search_fields=["user__first_name", "user__last_name", "user__username", "user__phone_number"],
        search_placeholder="جستجو در نام، نام کاربری یا شماره...",
    )

    if request.headers.get("HX-Request"):
        return render_table(request, table_ctx)

    return render(request, "notifications/broadcast_detail.html", {
        "broadcast": broadcast,
        "table": table_ctx,
        "stats": {
            "recipients_count": recipients_count,
            "sent_count": sent_count,
            "in_app_count": in_app_count,
            "failed_count": failed_count,
            "seen_count": seen_count,
            "clicked_count": clicked_count,
            "click_rate": click_rate,
        }
    })


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
