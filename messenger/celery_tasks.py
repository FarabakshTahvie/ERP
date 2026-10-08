import logging

from celery import shared_task
from django.conf import settings

from utils.models import PushDevice
from utils.push_notification import NajvaService

from . import cleanup, services
from .models import Message

logger = logging.getLogger(__name__)


def _transient(result):
    code = result.get("status_code")
    return code is None or code >= 500 or code == 429


@shared_task(bind=True, name="messenger.send_push", ignore_result=True, max_retries=2,
             soft_time_limit=40, time_limit=60)
def send_push_task(self, message_id):
    # مقدار بازگشتی نداریم. پیام گروه = یک درخواست بولک برای همه‌ی اعضا؛ خصوصی = فقط طرف مقابل.
    if not settings.NAJVA_ENABLED or getattr(settings, "BROADCAST_DRY_RUN", False):
        return None
    msg = (Message.objects.select_related("sender__messenger_profile", "conversation")
           .filter(pk=message_id, is_deleted=False).first())
    if msg is None:
        return None
    recipients = services.push_recipient_ids(msg)
    tokens = list(PushDevice.objects.filter(user_id__in=recipients, is_active=True)
                  .values_list("registration_id", flat=True))
    service = NajvaService()
    if not tokens or not service.configured:
        return None
    title, body = services.push_payload(msg)
    result = service.send(title=title, body=body, subscriber_tokens=tokens, url=services.push_url(msg), ttl=24)
    invalid = result.get("invalid_tokens") or []
    if invalid:
        PushDevice.objects.filter(registration_id__in=invalid).update(is_active=False)
    if not result.get("success") and _transient(result) and self.request.retries < self.max_retries:
        raise self.retry(countdown=10)
    return None


@shared_task(name="messenger.cleanup_old", ignore_result=True, soft_time_limit=250, time_limit=300)
def cleanup_old_task():
    # مقدار بازگشتی نداریم.
    removed = cleanup.purge_old()
    if removed:
        logger.info("messenger cleanup removed %s messages", removed)
    return None
