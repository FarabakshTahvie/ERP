import json
import uuid
from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.templatetags.static import static
from django.views.decorators.http import require_POST
from django.db.models import Q, Prefetch
from django.conf import settings

from .models import PushDevice, DeviceType
from .request_meta import parse_user_agent
from projects.models import Project, ProjectStage
from finance.models import Invoice
from notifications.models import Notification


def home_view(request):
    """
    داشبورد اصلی پرتال کاربران فرابخش.
    """
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    user = request.user
    party = getattr(user, "party", None)

    # فیلتر پروژه‌ها برای کاربر دارای party فقط partner یا owner باشد (هم‌خوان با project_progress)
    if party:
        q_filter = Q(partner=party) | Q(owner=party)
    else:
        q_filter = Q(created_by=user) | Q(assigned_technicians=user) | Q(participants__user=user)

    # مراحل را با Prefetch بخوان (فقط client_visible، مرتب بر اساس order)
    stages_qs = ProjectStage.objects.filter(client_visible=True).order_by('order')
    prefetch_stages = Prefetch('stages', queryset=stages_qs, to_attr='client_stages')

    projects_qs = Project.objects.filter(q_filter).select_related('partner', 'owner', 'location').prefetch_related(prefetch_stages).distinct().order_by('-created_at')
    projects_list = list(projects_qs[:6])

    # محاسبه done، total، percent و current برای هر پروژه
    for p in projects_list:
        c_stages = getattr(p, 'client_stages', [])
        total_stages = len(c_stages)
        done_stages = sum(1 for s in c_stages if s.status == ProjectStage.Status.DONE)
        percent = int((done_stages / total_stages * 100)) if total_stages > 0 else 0
        current_stage = next((s for s in c_stages if s.status == ProjectStage.Status.IN_PROGRESS), None)
        if not current_stage and c_stages:
            current_stage = next((s for s in c_stages if s.status != ProjectStage.Status.DONE), c_stages[-1])

        p.progress_total = total_stages
        p.progress_done = done_stages
        p.progress_percent = percent
        p.current_client_stage = current_stage

    # فاکتورها را با یک کوئری Invoice.objects.filter(project__in=..., billed_party=party) بگیر و به شکل دیکشنری بده
    invoices_map = {}
    if party and projects_list:
        invs = Invoice.objects.filter(project__in=projects_list, billed_party=party).select_related('project')
        for inv in invs:
            invoices_map[inv.project_id] = inv

    active_count = projects_qs.filter(status=Project.Status.IN_PROGRESS).count()
    completed_count = projects_qs.filter(status=Project.Status.COMPLETED).count()
    draft_count = projects_qs.filter(status=Project.Status.DRAFT).count()
    total_count = projects_qs.count()

    recent_notifications = Notification.objects.filter(user=user).order_by('-created_at')[:5]

    context = {
        'projects': projects_list,
        'invoices_map': invoices_map,
        'total_projects_count': total_count,
        'active_projects_count': active_count,
        'completed_projects_count': completed_count,
        'draft_projects_count': draft_count,
        'recent_notifications': recent_notifications,
        'party': party,
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
