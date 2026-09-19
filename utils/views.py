import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import PushDevice, DeviceType


def home_view(request):
    """
    داشبورد اصلی پرتال کاربران فرابخش.
    """
    from django.shortcuts import redirect
    if not request.user.is_authenticated:
        return redirect("accounts:login")

    user = request.user
    from projects.models import Project
    from notifications.models import Notification
    from django.db.models import Q

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


@csrf_exempt
@require_POST
def register_push_device(request):
    """
    API endpoint to register or update user push device token (e.g., from Najva or web push).
    Payload: { "token": "...", "browser": "Chrome", "os": "Windows", "device_type": "web" }
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({"status": "error", "message": "فرمت داده‌ها نامعتبر است."}, status=400)

    token = data.get('token')
    if not token:
        return JsonResponse({"status": "error", "message": "شناسه توکن (token) الزامی است."}, status=400)

    user = request.user if request.user.is_authenticated else None
    browser = data.get('browser')
    os_name = data.get('os')
    device_type = data.get('device_type', DeviceType.WEB)

    device, created = PushDevice.objects.update_or_create(
        registration_id=token,
        defaults={
            "user": user,
            "browser": browser,
            "os": os_name,
            "type": device_type,
            "is_active": True,
        }
    )

    return JsonResponse({
        "status": "success",
        "message": "دستگاه با موفقیت در دیتابیس ثبت شد.",
        "created": created,
        "device_id": device.id,
        "token": device.registration_id,
    })
