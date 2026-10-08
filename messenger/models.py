from django.conf import settings
from django.db import models
from django.db.models import Q


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
