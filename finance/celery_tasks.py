import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="finance.notify_expired_proformas", ignore_result=True, soft_time_limit=270, time_limit=300)
def notify_expired_proformas_task():
    from .deadline import notify_expired_proformas
    logger.info("notify_expired_proformas: %s queued", notify_expired_proformas())
    return None


@shared_task(name="finance.notify_cheques_due", ignore_result=True, soft_time_limit=270, time_limit=300)
def notify_cheques_due_task():
    from .services import notify_cheques_due
    logger.info("notify_cheques_due: %s queued", notify_cheques_due())
    return None
