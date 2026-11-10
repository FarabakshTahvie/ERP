import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="finance.notify_expired_proformas", ignore_result=True, soft_time_limit=270, time_limit=300)
def notify_expired_proformas_task():
    from .deadline import notify_expired_proformas
    logger.info("notify_expired_proformas: %s queued", notify_expired_proformas())
    return None
