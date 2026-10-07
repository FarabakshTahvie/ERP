import logging
import uuid

from celery import shared_task
from django.core.cache import cache

from notifications.broadcast import LOCK_KEY, LOCK_TTL, run_process_broadcasts

logger = logging.getLogger(__name__)


@shared_task(name="notifications.process_broadcasts", ignore_result=True, soft_time_limit=270, time_limit=300)
def process_broadcasts_task():
    # مقدار بازگشتی نداریم (Celery مقدار بازگشتی را در لاگ می‌نویسد).
    token = uuid.uuid4().hex
    if not cache.add(LOCK_KEY, token, LOCK_TTL):
        return None          # دور دیگری در حال کار است؛ بقیه را همان دور یا beat برمی‌دارد
    try:
        stats = run_process_broadcasts(max_seconds=200, heartbeat=lambda: cache.touch(LOCK_KEY, LOCK_TTL))
    finally:
        if cache.get(LOCK_KEY) == token:
            cache.delete(LOCK_KEY)
    logger.info("process_broadcasts: %s", stats)
    if stats["more"]:
        process_broadcasts_task.apply_async(countdown=1)
    return None
