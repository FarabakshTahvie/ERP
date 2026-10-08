import logging
import re
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone

from accounts.models import User
from core.capabilities import SPECIALTY_ACCOUNTANT, can

from .models import ChatState, Conversation, Message

logger = logging.getLogger(__name__)

MAIN_TITLE = "فراگرام"
MAX_TEXT = 4000
EDIT_WINDOW_HOURS = 48
RATE_LIMIT, RATE_WINDOW = 30, 60          # حداکثر ۳۰ پیام در دقیقه برای هر کاربر
PAGE, PAGE_NEW = 30, 100
# کاراکتر کنترلی و bidi-override (۲۰۲۰۲ تا ۲۰۲۲E و ۲۰۶۶ تا ۲۰۶۹) حذف می‌شوند؛ نیم‌فاصله و RLM/LRM می‌مانند
_CONTROL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]")


# ---------- کاربران و دسترسی ----------
def display_name(user):
    return (user.get_full_name() or user.username) if user is not None else "کاربر حذف‌شده"


def staff_qs():
    """کارکنان فعال (مدیر، تکنسین، سوپریوزر)؛ همان تعریف قابلیت messenger.use."""
    return User.objects.filter(is_active=True).filter(
        Q(role__in=[User.Role.ADMIN, User.Role.EMPLOYEE]) | Q(is_superuser=True))


def reach_all_qs():
    """معادل SQL قابلیت messenger.reach_all (تست مطابقت دارد)."""
    return staff_qs().filter(Q(role=User.Role.ADMIN) | Q(is_superuser=True)
                             | Q(specialties__name=SPECIALTY_ACCOUNTANT)).distinct()


def peers_for(user):
    qs = staff_qs().exclude(pk=user.pk)
    if not can(user, "messenger.reach_all"):
        qs = qs.filter(pk__in=reach_all_qs().values("pk"))
    return qs.order_by("first_name", "last_name", "username")


def can_direct(user, other):
    if user.pk == other.pk or not other.is_active:
        return False
    if not (can(user, "messenger.use") and can(other, "messenger.use")):
        return False
    return can(user, "messenger.reach_all") or can(other, "messenger.reach_all")


def ensure_main_group():
    conv = Conversation.objects.filter(is_main=True).first()
    if conv:
        return conv
    try:
        with transaction.atomic():
            return Conversation.objects.create(kind=Conversation.Kind.GROUP, title=MAIN_TITLE, is_main=True)
    except IntegrityError:
        return Conversation.objects.get(is_main=True)


def open_direct(user, other):
    if not can_direct(user, other):
        raise ValueError("امکان گفت‌وگو با این کاربر وجود ندارد.")
    low, high = sorted((user, other), key=lambda u: u.pk)
    conv, _ = Conversation.objects.get_or_create(kind=Conversation.Kind.DIRECT, user_low=low, user_high=high)
    return conv


def _peer_id(conv, user):
    return conv.user_high_id if conv.user_low_id == user.pk else conv.user_low_id


def get_conversation(user, conv_id):
    """گفت‌وگو یا Http404: گروه اصلی برای هر کارمند؛ خصوصی فقط برای همان دو نفر."""
    conv = Conversation.objects.filter(pk=conv_id).first()
    if conv is None or not can(user, "messenger.use"):
        raise Http404
    if conv.is_main:
        return conv
    if user.pk not in (conv.user_low_id, conv.user_high_id):
        raise Http404
    return conv


# ---------- متن ----------
def clean_text(raw):
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text).strip()
    if len(text) > MAX_TEXT:
        raise ValueError("متن پیام حداکثر ۴۰۰۰ کاراکتر است.")
    return text


def _clean_uid(raw):
    try:
        return str(uuid.UUID(str(raw or "").strip()))
    except ValueError:
        return ""


def _rate_limit(user):
    key = f"msgr:rate:{user.pk}"
    cache.add(key, 0, RATE_WINDOW)
    if cache.incr(key) > RATE_LIMIT:
        raise ValueError("تعداد پیام‌ها در یک دقیقه زیاد است؛ کمی صبر کنید.")


# ---------- خروجی ----------
def _snippet(m):
    if m is None:
        return ""
    return "پیام حذف شد" if m.is_deleted else m.text[:80]


def serialize_message(m, viewer):
    r = m.reply_to
    return {
        "id": m.id,
        "conv_id": m.conversation_id,
        "sender": {"id": m.sender_id, "name": display_name(m.sender)},
        "mine": m.sender_id == viewer.pk,
        "uid": m.client_uid if m.sender_id == viewer.pk else "",
        "text": "" if m.is_deleted else m.text,
        "deleted": m.is_deleted,
        "edited": bool(m.edited_at),
        "reply": ({"id": r.id, "name": display_name(r.sender), "snippet": _snippet(r)} if r else None),
        "at": timezone.localtime(m.created_at).isoformat(),
        "ts": m.created_at.timestamp(),
    }


def _item(conv, user, peer=None):
    main = conv is not None and conv.is_main
    last = conv.last_message if conv is not None else None
    return {
        "key": "main" if main else f"u{peer.pk}",
        "is_main": main,
        "conv_id": conv.pk if conv is not None else None,
        "peer_id": peer.pk if peer is not None else None,
        "title": conv.title if main else display_name(peer),
        "last": ({"text": _snippet(last), "at": timezone.localtime(last.created_at).isoformat(),
                  "mine": last.sender_id == user.pk, "sender": display_name(last.sender)}
                 if last is not None else None),
        "ts": conv.last_message_at.timestamp() if conv is not None and conv.last_message_at else None,
        "unread": getattr(conv, "unread", 0) if conv is not None else 0,
        "muted": bool(getattr(conv, "is_muted", False)) if conv is not None else False,
    }


def inbox(user):
    """لیست چت‌ها: گروه اصلی همیشه اول؛ بقیه بر اساس جدیدترین پیام؛ بدون پیام‌ها آخر (الفبایی)."""
    ensure_main_group()
    state = ChatState.objects.filter(conversation=OuterRef("pk"), user=user)
    unread_sq = (Message.objects.filter(conversation=OuterRef("pk"), is_deleted=False, id__gt=OuterRef("lr"))
                 .exclude(sender=user).order_by().values("conversation_id")
                 .annotate(n=Count("id")).values("n"))
    convs = list(
        Conversation.objects.filter(Q(is_main=True) | Q(user_low=user) | Q(user_high=user))
        .select_related("last_message__sender")
        .annotate(lr=Coalesce(Subquery(state.values("last_read_id")[:1]), Value(0)),
                  is_muted=Coalesce(Subquery(state.values("muted")[:1]), Value(False)))
        .annotate(unread=Coalesce(Subquery(unread_sq), Value(0))))
    main = next(c for c in convs if c.is_main)
    by_peer = {_peer_id(c, user): c for c in convs if not c.is_main}
    items = [_item(main, user)]
    rest = [_item(by_peer.get(p.pk), user, peer=p) for p in peers_for(user)]
    rest.sort(key=lambda i: (i["ts"] is None, -(i["ts"] or 0), i["title"]))
    items += rest
    return {"items": items, "total_unread": sum(i["unread"] for i in items if not i["muted"])}


def unread_total(user):
    """مجموع نخوانده‌های بی‌صدانشده (برای نشان کنار آیکون هدر)؛ باید با inbox()["total_unread"] برابر باشد."""
    state = ChatState.objects.filter(conversation=OuterRef("conversation_id"), user=user)
    return (Message.objects.filter(is_deleted=False)
            .filter(Q(conversation__is_main=True) | Q(conversation__user_low=user) | Q(conversation__user_high=user))
            .exclude(sender=user)
            .annotate(lr=Coalesce(Subquery(state.values("last_read_id")[:1]), Value(0)),
                      mu=Coalesce(Subquery(state.values("muted")[:1]), Value(False)))
            .filter(id__gt=F("lr"), mu=False)
            .count())


def chat_meta(user, conv):
    """سرتیتر صفحه‌ی چت."""
    muted = ChatState.objects.filter(conversation=conv, user=user, muted=True).exists()
    if conv.is_main:
        return {"key": "main", "title": conv.title, "is_main": True, "members": staff_qs().count(),
                "sub": "", "muted": muted}
    peer_id = _peer_id(conv, user)
    peer = User.objects.filter(pk=peer_id).first()
    names = list(peer.specialties.values_list("name", flat=True)) if peer else []
    is_boss = bool(peer and (peer.is_superuser or peer.role == User.Role.ADMIN))
    return {"key": f"u{peer_id}", "title": display_name(peer), "is_main": False, "members": None,
            "sub": "مدیر" if is_boss else ("، ".join(names) or "تکنسین"), "muted": muted}


def _since_dt(since):
    try:
        return datetime.fromtimestamp(float(since), tz=dt_timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def fetch_messages(user, conv, *, after=None, before=None, since=None):
    """after: پیام‌های تازه‌تر (+ ویرایش/حذف‌های اخیر با since) | before: صفحه‌ی قدیمی‌تر | هیچ‌کدام: آخرین صفحه."""
    now = timezone.now().timestamp()
    base = conv.messages.select_related("sender", "reply_to__sender")
    updates, has_more = [], False
    if after is not None:
        rows = list(base.filter(id__gt=after).order_by("id")[:PAGE_NEW])
        since_dt = _since_dt(since) if since is not None else None
        if since_dt is not None:
            updates = list(base.filter(id__lte=after, id__gt=max(after - 300, 0), updated_at__gt=since_dt))
    else:
        qs = base.filter(id__lt=before) if before is not None else base
        rows = list(qs.order_by("-id")[:PAGE + 1])
        has_more = len(rows) > PAGE
        rows = rows[:PAGE][::-1]
    peer_read = None
    if not conv.is_main:
        peer_read = (ChatState.objects.filter(conversation=conv).exclude(user=user)
                     .values_list("last_read_id", flat=True).first()) or 0
    return {
        "messages": [serialize_message(m, user) for m in rows],
        "updates": [serialize_message(m, user) for m in updates],
        "has_more": has_more, "now": now, "peer_read_id": peer_read,
    }


# ---------- نوشتن ----------
def mark_read(user, conv, up_to=None):
    latest = conv.messages.aggregate(m=Max("id"))["m"] or 0
    up_to = latest if up_to is None else min(int(up_to), latest)
    state, _ = ChatState.objects.get_or_create(conversation=conv, user=user)
    ChatState.objects.filter(pk=state.pk, last_read_id__lt=up_to).update(last_read_id=up_to)


def set_muted(user, conv, muted):
    state, _ = ChatState.objects.get_or_create(conversation=conv, user=user)
    ChatState.objects.filter(pk=state.pk).update(muted=bool(muted))


def kick_push(message_id):
    """بعد از commit صدا زده می‌شود. خطای صف (مثلاً ردیس پایین) فقط لاگ می‌شود و پیام ثبت‌شده می‌ماند."""
    try:
        from .celery_tasks import send_push_task
        send_push_task.delay(message_id)
    except Exception:
        logger.exception("messenger push could not be queued")


@transaction.atomic
def send_message(user, conv, *, text, reply_to_id=None, client_uid=""):
    """خروجی: (پیام، ساخته_شد؟). با client_uid تکراری همان پیام قبلی برمی‌گردد."""
    if not can(user, "messenger.use"):
        raise ValueError("شما اجازه‌ی استفاده از پیام‌رسان را ندارید.")
    if not conv.is_main:
        other = User.objects.filter(pk=_peer_id(conv, user), is_active=True).first()
        if other is None or not can_direct(user, other):
            raise ValueError("امکان ارسال پیام به این کاربر وجود ندارد.")
    text = clean_text(text)
    if not text:
        raise ValueError("متن پیام خالی است.")
    uid = _clean_uid(client_uid)
    if uid:
        existing = Message.objects.filter(sender=user, client_uid=uid).first()
        if existing:
            return existing, False
    _rate_limit(user)
    reply = None
    if reply_to_id:
        reply = Message.objects.filter(pk=reply_to_id, conversation=conv).first()
        if reply is None:
            raise ValueError("پیامی که به آن پاسخ می‌دهید پیدا نشد.")
    try:
        with transaction.atomic():
            msg = Message.objects.create(conversation=conv, sender=user, text=text, reply_to=reply, client_uid=uid)
    except IntegrityError:   # دو ارسال هم‌زمان با یک client_uid
        return Message.objects.get(sender=user, client_uid=uid), False
    Conversation.objects.filter(pk=conv.pk).update(last_message=msg, last_message_at=msg.created_at)
    mark_read(user, conv, msg.pk)
    transaction.on_commit(lambda: kick_push(msg.pk))
    return msg, True


def _editable(user, message_id):
    m = (Message.objects.select_for_update(of=("self",)).select_related("conversation")
         .filter(pk=message_id).first())
    if m is None:
        raise Http404
    get_conversation(user, m.conversation_id)       # غیرعضو ← ۴۰۴
    return m


@transaction.atomic
def edit_message(user, message_id, text):
    m = _editable(user, message_id)
    if m.sender_id != user.pk:
        raise ValueError("فقط فرستنده می‌تواند پیام را ویرایش کند.")
    if m.is_deleted:
        raise ValueError("پیام حذف شده است.")
    if timezone.now() - m.created_at > timedelta(hours=EDIT_WINDOW_HOURS):
        raise ValueError("بیش از ۴۸ ساعت از ارسال پیام گذشته و ویرایش ممکن نیست.")
    text = clean_text(text)
    if not text:
        raise ValueError("متن پیام خالی است.")
    if text != m.text:
        m.text, m.edited_at = text, timezone.now()
        m.save(update_fields=["text", "edited_at", "updated_at"])
    return m


@transaction.atomic
def delete_message(user, message_id):
    """فرستنده؛ و مدیر فقط در گروه اصلی (نظارت). حذف نرم است و متن پاک می‌شود."""
    m = _editable(user, message_id)
    if m.sender_id != user.pk and not (m.conversation.is_main and can(user, "dashboard.manager")):
        raise ValueError("شما اجازه‌ی حذف این پیام را ندارید.")
    if not m.is_deleted:
        m.is_deleted, m.text = True, ""
        m.save(update_fields=["is_deleted", "text", "updated_at"])
    return m


# ---------- پوش ----------
def push_recipient_ids(msg):
    conv = msg.conversation
    if conv.is_main:
        ids = set(staff_qs().values_list("pk", flat=True))
    else:
        ids = set(staff_qs().filter(pk__in=[conv.user_low_id, conv.user_high_id]).values_list("pk", flat=True))
    ids.discard(msg.sender_id)
    muted = set(ChatState.objects.filter(conversation=conv, muted=True, user_id__in=ids)
                .values_list("user_id", flat=True))
    return ids - muted


def push_payload(msg):
    name = display_name(msg.sender)
    title = f"{MAIN_TITLE} · {name}" if msg.conversation.is_main else name
    return title, (msg.text[:120] or "پیام جدید")


def push_url(msg):
    return f"{settings.SITE_BASE_URL.rstrip('/')}/messenger/c/{msg.conversation_id}/"
