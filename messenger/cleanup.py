from datetime import timedelta

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from .models import Attachment, Conversation, Message

RETENTION_DAYS = 183          # حدود شش ماه
BATCH, MAX_BATCHES = 200, 50


def _refresh_last(conv_id):
    last = Message.objects.filter(conversation_id=conv_id).order_by("-id").first()
    Conversation.objects.filter(pk=conv_id).update(
        last_message=last, last_message_at=last.created_at if last else None)


def purge_old(*, now=None):
    """فقط پیام‌ها و فایل‌های پیام‌رسان؛ پیام پین‌شده می‌ماند. خروجی: تعداد پیام پاک‌شده."""
    cutoff = (now or timezone.now()) - timedelta(days=RETENTION_DAYS)
    removed = 0
    for _ in range(MAX_BATCHES):
        paths = []
        with transaction.atomic():
            ids = list(Message.objects.filter(created_at__lt=cutoff, pinned_at__isnull=True)
                       .order_by("id").values_list("pk", flat=True)[:BATCH])
            if not ids:
                break
            conv_ids = set(Message.objects.filter(pk__in=ids).values_list("conversation_id", flat=True))
            for a in Attachment.objects.filter(message_id__in=ids):
                paths.append(a.file.name)
                if a.thumb:
                    paths.append(a.thumb.name)
            Message.objects.filter(pk__in=ids).delete()        # پیوست‌ها cascade می‌شوند
            for cid in conv_ids:
                _refresh_last(cid)
        for p in paths:                                         # فایل‌ها بعد از commit پاک می‌شوند
            default_storage.delete(p)
        removed += len(ids)
    return removed