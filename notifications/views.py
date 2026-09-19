from django.http import HttpResponseRedirect, Http404
from django.utils import timezone
from .models import Notification, NotificationClickEvent


def track_and_redirect(request, notification_uuid):
    try:
        notification = Notification.objects.get(uuid=notification_uuid)
    except Notification.DoesNotExist:
        raise Http404

    NotificationClickEvent.objects.create(
        notification=notification,
        channel=request.GET.get("ch", "push"),
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    if notification.seen_at is None:
        notification.seen_at = timezone.now()
        notification.status = Notification.Status.SEEN
        notification.save(update_fields=["seen_at", "status"])

    return HttpResponseRedirect(notification.real_target_url or "/")
