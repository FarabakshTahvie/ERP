import os
import re
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


def _ext(name):
    ext = os.path.splitext(name or "")[1].lower().lstrip(".")
    ext = re.sub(r"[^a-z0-9]", "", ext)[:8]
    return f".{ext}" if ext else ""


def attachment_path(instance, filename):
    return f"messenger/{instance.conversation_id}/{uuid.uuid4().hex}{_ext(filename)}"


def thumb_path(instance, filename):
    return f"messenger/{instance.conversation_id}/t_{uuid.uuid4().hex}.webp"


class Conversation(models.Model):
    """گروه اصلی (is_main) یا گفت‌وگوی خصوصی بین دو نفر (user_low.pk < user_high.pk)."""

    class Kind(models.TextChoices):
        GROUP = "group", "گروه"
        DIRECT = "direct", "خصوصی"

    kind = models.CharField(max_length=10, choices=Kind.choices)
    title = models.CharField(max_length=100, blank=True)
    is_main = models.BooleanField(default=False)
    user_low = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.CASCADE, related_name="+")
    user_high = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="+")
    last_message = models.ForeignKey("Message", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گفت‌وگو"
        verbose_name_plural = "گفت‌وگوها"
        constraints = [
            models.UniqueConstraint(fields=["is_main"], condition=Q(is_main=True),
                                    name="uniq_main_conversation"),
            models.UniqueConstraint(fields=["user_low", "user_high"], condition=Q(kind="direct"),
                                    name="uniq_direct_pair"),
        ]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name="+")
    text = models.TextField(blank=True)
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    client_uid = models.CharField(max_length=36, blank=True)
    is_deleted = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   # فقط با save() عوض می‌شود، نه update()
    pinned_at = models.DateTimeField(null=True, blank=True)     # با update() ست می‌شود تا updated_at (نشان ویرایش) عوض نشود
    pinned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["conversation", "id"]),
            models.Index(fields=["conversation", "updated_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["sender", "client_uid"], condition=~Q(client_uid=""),
                                    name="uniq_message_client_uid"),
        ]


class ChatState(models.Model):
    """خوانده‌شدن و بی‌صدا بودن هر کاربر برای هر گفت‌وگو (ردیف به‌صورت تنبل ساخته می‌شود)."""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="states")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    last_read_id = models.PositiveBigIntegerField(default=0)
    muted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["conversation", "user"], name="uniq_chat_state"),
        ]


class Attachment(models.Model):
    """پیوست پیام. تا وقتی message خالی است «یتیم» است (آپلود شده ولی هنوز در پیامی نیامده)."""

    class Kind(models.TextChoices):
        IMAGE = "image", "عکس"
        VIDEO = "video", "ویدیو"
        AUDIO = "audio", "صوت"
        VOICE = "voice", "پیام صوتی"
        FILE = "file", "فایل"

    message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="attachments")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="+")
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                 related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    file = models.FileField(upload_to=attachment_path, max_length=200)
    thumb = models.FileField(upload_to=thumb_path, max_length=200, blank=True)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "پیوست"
        verbose_name_plural = "پیوست‌ها"
        ordering = ["order", "id"]
        indexes = [models.Index(fields=["message", "order"])]
