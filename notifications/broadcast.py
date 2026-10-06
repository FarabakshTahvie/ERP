import os
import re
import json
import hashlib
import logging
import secrets
from PIL import Image
from io import BytesIO
from django.conf import settings
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import resolve, Resolver404
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from accounts.models import User
from utils.sms import SMSService
from utils.push_notification import NajvaService
from notifications.models import Broadcast, Notification, NotificationType

logger = logging.getLogger(__name__)

MAX_PUSH_RECIPIENTS = 500
MAX_SMS_RECIPIENTS = 200

ASSET_RE = re.compile(r"^[0-9a-f]{32}\.(webp|png|jpg)$")
ICON_MAX, IMAGE_MAX = 100 * 1024, 2 * 1024 * 1024
MIME = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg"}

SMS_GLOBAL = {10, 11, 12, 13, 14, 101, 102, 123}
SMS_RATE = {20}
NAJVA_GLOBAL_HTTP = {403, 414, 416, 418}
SIGNATURE = "فرابخش تهویه"
SENT = {"push": Notification.Status.PUSH_SENT, "sms": Notification.Status.SMS_SENT}


def read_asset(name, max_bytes):
    if not name:
        return None
    if not ASSET_RE.match(name):
        raise ValueError("نام فایل نامعتبر است.")
    path = f"broadcast/{name}"
    if not default_storage.exists(path):
        raise ValueError("فایل پیدا نشد.")
    with default_storage.open(path, "rb") as f:
        data = f.read()
    if len(data) > max_bytes:
        raise ValueError("حجم فایل از سقف مجاز بیشتر است.")
    return (name, data, MIME[name.rsplit(".", 1)[1]])


def save_broadcast_asset(uploaded_file, *, kind):
    if not uploaded_file:
        return ""
    
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise ValueError("فرمت تصویر نامعتبر است. فقط JPG, PNG, WEBP مجاز هستند.")

    raw_data = uploaded_file.read()
    if kind == "image":
        if len(raw_data) > IMAGE_MAX:
            raise ValueError("حجم تصویر نباید بیش از ۲ مگابایت باشد.")
        try:
            img = Image.open(BytesIO(raw_data))
            img.verify()
            img = Image.open(BytesIO(raw_data))
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            out = BytesIO()
            fmt = "WEBP" if ext == ".webp" else "JPEG"
            img.save(out, format=fmt, quality=85)
            final_bytes = out.getvalue()
            final_ext = "webp" if fmt == "WEBP" else "jpg"
        except Exception:
            raise ValueError("تصویر نامعتبر یا خراب است.")
    elif kind == "icon":
        try:
            img = Image.open(BytesIO(raw_data))
            img.thumbnail((192, 192))
            out = BytesIO()
            img.save(out, format="PNG")
            final_bytes = out.getvalue()
            final_ext = "png"
            if len(final_bytes) > ICON_MAX:
                raise ValueError("حجم آیکون پس از بهینه‌سازی بیش از ۱۰۰ کیلوبایت است.")
        except Exception:
            raise ValueError("آیکون نامعتبر است.")
    else:
        raise ValueError("نوع فایل نامعتبر است.")

    random_name = f"{secrets.token_hex(16)}.{final_ext}"
    save_path = os.path.join("broadcast", random_name)
    default_storage.save(save_path, ContentFile(final_bytes))
    return random_name


def load_assets(broadcast):
    icon_tuple = None
    if broadcast.icon_name:
        try:
            icon_tuple = read_asset(broadcast.icon_name, ICON_MAX)
        except Exception:
            icon_tuple = None
    
    if not icon_tuple:
        default_icon_path = os.path.join(settings.BASE_DIR, "static", "icons", "icon-192.png")
        if os.path.exists(default_icon_path):
            with open(default_icon_path, "rb") as f:
                d_bytes = f.read()
            icon_tuple = ("icon-192.png", d_bytes, "image/png")

    image_tuple = None
    if broadcast.image_name:
        try:
            image_tuple = read_asset(broadcast.image_name, IMAGE_MAX)
        except Exception:
            image_tuple = None

    return {"icon": icon_tuple, "image": image_tuple}


def parse_audience(post):
    kind = post.get("audience_kind", "")
    raw = post.getlist("audience_ids")
    if kind == "all_staff":
        ids = []
    elif kind in ("specialty", "users"):
        ids = sorted({int(x) for x in raw if str(x).isdigit()})
    elif kind == "role":
        ids = sorted(set(raw) & {"client", "partner"})
    else:
        raise ValueError("نوع مخاطب را انتخاب کنید.")
    if kind != "all_staff" and not ids:
        raise ValueError("مخاطب را انتخاب کنید.")
    return kind, ids


def audience_label_for(kind, ids):
    if kind == "all_staff":
        return "همه‌ی کارکنان (مدیران و تکنسین‌ها)"
    elif kind == "specialty":
        from core.models import Specialty
        specs = list(Specialty.objects.filter(id__in=ids).values_list("name", flat=True))
        return f"تخصص: {', '.join(specs)}"
    elif kind == "role":
        role_names = []
        if "client" in ids:
            role_names.append("کارفرما")
        if "partner" in ids:
            role_names.append("شریک تجاری")
        return f"مشتریان و شرکا ({', '.join(role_names)})"
    elif kind == "users":
        return f"{len(ids)} کاربر انتخابی"
    return "سایر مخاطبان"


def resolve_audience(kind, ids, channel):
    User = get_user_model()
    queryset = User.objects.filter(is_active=True)

    if kind == "all_staff":
        queryset = queryset.filter(role__in=["manager", "employee"])
    elif kind == "specialty":
        queryset = queryset.filter(role="employee", specialties__id__in=ids)
    elif kind == "role":
        from django.db.models import Q
        query = Q()
        if "client" in ids:
            query |= Q(role="client", party__isnull=False)
        if "partner" in ids:
            query |= Q(role="partner", party__isnull=False)
        queryset = queryset.filter(query)
    elif kind == "users":
        queryset = queryset.filter(id__in=ids)
    else:
        return []

    users = list(queryset.distinct())
    if channel == "sms":
        users = [u for u in users if u.phone_number]
    return users


def validate_link(path):
    if not path:
        return True
    if not path.startswith("/") or path.startswith("//"):
        return False
    try:
        resolve(path)
        return True
    except Resolver404:
        return False


def calculate_digest(body, audience_kind, audience_ids, image_name, icon_name, ttl_hours, buttons, channel, resolved_user_ids):
    payload = {
        "body": body,
        "audience_kind": audience_kind,
        "audience_ids": sorted(audience_ids or []),
        "image_name": image_name or "",
        "icon_name": icon_name or "",
        "ttl_hours": ttl_hours,
        "buttons": buttons or [],
        "channel": channel,
        "resolved_user_ids": sorted(resolved_user_ids or []),
    }
    dumped = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def validate_content(channel, title, body, ttl_hours, image_name, icon_name, buttons):
    if channel == "push":
        if not title or len(title) > 250:
            raise ValueError("عنوان پوش الزامی و حداکثر ۲۵۰ کاراکتر است.")
        if not body or len(body) > 400:
            raise ValueError("متن پوش الزامی و حداکثر ۴۰۰ کاراکتر است.")
    elif channel == "sms":
        if not body or len(body) > 320:
            raise ValueError("متن پیامک الزامی و حداکثر ۳۲۰ کاراکتر است.")
    
    if not (1 <= ttl_hours <= 168):
        raise ValueError("مدت ماندگاری باید بین ۱ تا ۱۶۸ ساعت باشد.")
    
    if image_name and not ASSET_RE.match(image_name):
        raise ValueError("تصویر نامعتبر است.")
    if icon_name and not ASSET_RE.match(icon_name):
        raise ValueError("آیکون نامعتبر است.")
    
    if buttons:
        if not isinstance(buttons, list) or len(buttons) > 2:
            raise ValueError("حداکثر ۲ دکمه مجاز است.")
        for btn in buttons:
            btitle = btn.get("title", "")
            bpath = btn.get("path", "")
            if not btitle or len(btitle) > 20:
                raise ValueError("عنوان دکمه الزامی و حداکثر ۲۰ کاراکتر است.")
            if not validate_link(bpath):
                raise ValueError("مسیر دکمه نامعتبر است.")


def channel_open(channel):
    if getattr(settings, "BROADCAST_DRY_RUN", False):
        return True
    return getattr(settings, "NAJVA_ENABLED", False) if channel == "push" else getattr(settings, "SMS_FREE_TEXT_ENABLED", False)


def _mark(n, status, *, error="", ref=""):
    n.status = status
    n.error_text = error[:255]
    n.provider_ref = ref[:64]
    t = now()
    if status == Notification.Status.PUSH_SENT:
        n.push_sent_at = t
    elif status == Notification.Status.SMS_SENT:
        n.sms_sent_at = t
    n.save(update_fields=["status", "error_text", "provider_ref", "push_sent_at", "sms_sent_at"])


def deliver_one(n, assets):
    b = n.broadcast
    if b.is_dry_run:
        _mark(n, SENT[b.channel], error="آزمایشی")
        return False
    if not channel_open(b.channel):
        return True
    return _sms(n, b) if b.channel == "sms" else _push(n, b, assets)


def _sms(n, b):
    phone = n.user.phone_number
    if not phone:
        _mark(n, Notification.Status.FAILED, error="فاقد شماره همراه")
        return False
    
    text = b.body + (f"\n{n.tracking_url}" if n.tracking_url else "") + f"\n{SIGNATURE}"
    r = SMSService().send_text(mobile=phone, message=text)
    data = r.get("data") if isinstance(r.get("data"), dict) else {}
    code = data.get("status")
    
    if r.get("success"):
        msg_id = r.get("message_id")
        if not msg_id or msg_id == 0:
            _mark(n, Notification.Status.FAILED, error="شماره در لیست سیاه یا نامعتبر است")
            return False
        _mark(n, Notification.Status.SMS_SENT, ref=str(msg_id))
        return False
    
    if code in SMS_RATE or r.get("http_status") == 429:
        return True
    
    _mark(n, Notification.Status.FAILED, error=str(r.get("error") or "خطای ارسال"))
    return code in SMS_GLOBAL


def _push(n, b, assets):
    from utils.models import PushDevice
    tokens = list(PushDevice.objects.filter(user=n.user, is_active=True).values_list("registration_id", flat=True))
    if not tokens:
        _mark(n, Notification.Status.IN_APP)
        return False

    click_url = f"{n.tracking_url}?ch=push" if n.tracking_url else settings.SITE_BASE_URL
    buttons = []
    for btn in (b.buttons or []):
        buttons.append({
            "title": btn.get("title", ""),
            "url": f"{settings.SITE_BASE_URL.rstrip('/')}{btn.get('path', '/')}"[:80]
        })

    result = NajvaService().send(
        title=b.title or "فرابخش تهویه",
        body=b.body,
        subscriber_tokens=tokens,
        url=click_url,
        ttl=b.ttl_hours,
        icon=assets.get("icon"),
        image=assets.get("image"),
        buttons=buttons,
    )

    invalid = result.get("invalid_tokens") or []
    if invalid:
        PushDevice.objects.filter(registration_id__in=invalid).update(is_active=False)
        if len(invalid) == len(tokens):
            _mark(n, Notification.Status.IN_APP, error="دستگاه معتبری یافت نشد")
            return False

    status_code = result.get("status_code")
    if status_code in NAJVA_GLOBAL_HTTP:
        _mark(n, Notification.Status.FAILED, error=result.get("error", "خطای گلوبال نجوا"))
        return True

    if not result.get("success") and not status_code and "najva not configured" in str(result.get("error")):
        return True

    ok = bool(result.get("success"))
    if ok:
        _mark(n, Notification.Status.PUSH_SENT, ref=str(result.get("request_id") or ""))
    else:
        _mark(n, Notification.Status.FAILED, error=str(result.get("error") or "خطای ارسال پوش"))
    
    return False


def create_broadcast(*, channel, title, body, link_path, icon_name, image_name, ttl_hours, audience_kind, audience_ids, created_by, buttons=None, digest=None):
    if channel == "sms":
        if not channel_open("sms"):
            raise ValueError("پیامک بدون قالب غیرفعال است.")
    elif channel == "push":
        if not channel_open("push"):
            raise ValueError("پوش نوتیفیکیشن غیرفعال است.")

    if link_path and not validate_link(link_path):
        raise ValueError("لینک وارد شده نامعتبر یا خارجی است.")

    buttons = buttons or []
    validate_content(channel, title, body, ttl_hours, image_name, icon_name, buttons)

    users = resolve_audience(audience_kind, audience_ids, channel)
    resolved_user_ids = [u.id for u in users]
    audience_label = audience_label_for(audience_kind, audience_ids)

    computed_digest = calculate_digest(body, audience_kind, audience_ids, image_name, icon_name, ttl_hours, buttons, channel, resolved_user_ids)
    if digest != computed_digest:
        raise ValueError("محتوای پیام یا گیرندگان تغییر کرده است. لطفاً پیش‌نمایش را بررسی کنید.")

    if channel == "sms" and len(users) > MAX_SMS_RECIPIENTS:
        raise ValueError(f"تعداد گیرندگان پیامک بیش از حد مجاز است (حداکثر {MAX_SMS_RECIPIENTS} کاربر).")
    if channel == "push" and len(users) > MAX_PUSH_RECIPIENTS:
        raise ValueError(f"تعداد گیرندگان پوش بیش از حد مجاز است (حداکثر {MAX_PUSH_RECIPIENTS} کاربر).")
    if not users:
        raise ValueError("گیرنده‌ای برای این ارسال پیدا نشد.")

    skipped_count = 0
    if channel == "sms":
        full_audience = resolve_audience(audience_kind, audience_ids, "push")
        skipped_count = len(full_audience) - len(users)

    is_dry_run = getattr(settings, "BROADCAST_DRY_RUN", False)

    with transaction.atomic():
        broadcast = Broadcast.objects.create(
            channel=channel,
            title=title if channel == "push" else "",
            body=body,
            link_path=link_path,
            icon_name=icon_name,
            image_name=image_name,
            ttl_hours=ttl_hours,
            buttons=buttons,
            audience_kind=audience_kind,
            audience_ids=audience_ids or [],
            audience_label=audience_label,
            recipients_count=len(users),
            skipped_count=skipped_count,
            is_dry_run=is_dry_run,
            created_by=created_by
        )

        notifications = []
        for user in users:
            notifications.append(Notification(
                notification_type=NotificationType.BROADCAST,
                user=user,
                title=title if channel == "push" else "پیام همگانی",
                body=body,
                real_target_url=link_path or "/",
                status=Notification.Status.PENDING,
                broadcast=broadcast
            ))
        if notifications:
            Notification.objects.bulk_create(notifications)

    return broadcast


def retry_failed(broadcast):
    with transaction.atomic():
        updated = Notification.objects.filter(
            broadcast=broadcast,
            status=Notification.Status.FAILED
        ).update(status=Notification.Status.PENDING, error_text="", provider_ref="")
        return updated
