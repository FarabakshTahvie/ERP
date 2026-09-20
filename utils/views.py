import json
import uuid
from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.templatetags.static import static
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.conf import settings

from .models import PushDevice, DeviceType
from .request_meta import parse_user_agent
from projects.models import Project
from notifications.models import Notification


def home_view(request):
    """
    داشبورد اصلی پرتال کاربران فرابخش.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    user = request.user

    # بارگذاری پروژه‌های مرتبط با کاربر
    if user.party:
        q_filter = Q(partner=user.party) | Q(owner=user.party) | Q(participants__party=user.party)
    else:
        q_filter = Q(created_by=user) | Q(assigned_technicians=user) | Q(participants__user=user)

    projects = Project.objects.filter(q_filter).select_related('partner', 'owner', 'location').distinct().order_by('-created_at')

    active_count = projects.filter(status=Project.Status.IN_PROGRESS).count()
    completed_count = projects.filter(status=Project.Status.COMPLETED).count()
    draft_count = projects.filter(status=Project.Status.DRAFT).count()

    recent_notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]

    context = {
        'projects': projects[:6],
        'total_projects_count': projects.count(),
        'active_projects_count': active_count,
        'completed_projects_count': completed_count,
        'draft_projects_count': draft_count,
        'recent_notifications': recent_notifications,
    }
    return render(request, "client_home.html", context)


@require_POST
def register_push_device(request):
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "ابتدا وارد شوید."}, status=401)
    try:
        data = json.loads(request.body.decode("utf-8"))
        token = str(data.get("token", "")).strip()
        uuid.UUID(token)                      # توکن نجوا UUID است
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"status": "error", "message": "توکن نامعتبر است."}, status=400)

    ua = parse_user_agent(request)            # مرورگر/سیستم‌عامل از سرور، نه از کلاینت
    device, created = PushDevice.objects.update_or_create(
        registration_id=token,
        defaults={
            "user": request.user,
            "browser": ua["browser"],
            "os": ua["os"],
            "type": DeviceType.WEB,
            "is_active": True,
        },
    )
    return JsonResponse({"status": "success", "created": created, "device_id": device.id})


def manifest_view(request):
    manifest_data = {
        "name": "فرابخش تهویه",
        "short_name": "فرابخش",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "dir": "rtl",
        "lang": "fa",
        "background_color": "#F3F6F6",
        "theme_color": "#0E7C86",
        "icons": [
            {
                "src": static("icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
        ],
    }
    return JsonResponse(manifest_data, content_type="application/manifest+json")


def najva_service_worker(request):
    """
    سرویس ورکر نجوا از ریشه دامنه
    """
    NAJVA_SW_JS = "importScripts('https://van.najva.com/static/js/service-worker.js');\n"
    response = HttpResponse(NAJVA_SW_JS, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response
