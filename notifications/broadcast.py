import os
import re
import json
import hashlib
import logging
import secrets
import time
from io import BytesIO
from datetime import timedelta
from urllib.parse import urlsplit
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import resolve, Resolver404
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from accounts.models import User
from utils.sms import SMSService
from utils.push_notification import NajvaService
from notifications.models import Broadcast, Notification, NotificationType, _new_short_code

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

WAIT, FAIL_ALL = "wait", "fail_all"
RETRY_MARK = "ارسال مجدد"      # ردیف‌های ارسال‌دوباره با این نشانه از انقضا معاف‌اند تا دوباره ارسال شوند
RAW_MAX = 10 * 1024 * 1024
BATCH = 40
LOCK_KEY = "lock:process_broadcasts"
LOCK_TTL = 90


class AssetError(ValueError):
    """آیکون یا تصویر پیام در دسترس نیست."""


def read_asset(name, max_bytes):
    if not name:
        return None
    if not ASSET_RE.match(name):
        raise AssetError("نام فایل نامعتبر است.")
    path = f"broadcast/{name}"
    if not default_storage.exists(path):
        raise AssetError("فایل آیکون یا تصویر پیام پیدا نشد.")
    with default_storage.open(path, "rb") as f:
        data = f.read()
    if len(data) > max_bytes:
        raise AssetError("حجم فایل از سقف مجاز بیشتر است.")
    return (name, data, MIME[name.rsplit(".", 1)[1]])


def _flatten_white(img):
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return img.convert("RGB")


def save_broadcast_asset(uploaded_file, *, kind):
    if not uploaded_file:
        return ""
    if kind not in ("icon", "image"):
        raise ValueError("نوع فایل نامعتبر است.")
    label = "آیکون" if kind == "icon" else "تصویر"
    ext = os.path.splitext(uploaded_file.name or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        raise ValueError("فرمت تصویر نامعتبر است؛ فقط JPG، PNG یا WEBP.")
    if uploaded_file.size > RAW_MAX:
        raise ValueError(f"حجم {label} بیش از حد بزرگ است.")
    try:
        img = Image.open(uploaded_file)
        img.load()
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError, SyntaxError, EOFError, Image.DecompressionBombError):
        raise ValueError(f"{label} نامعتبر یا خراب است.")

    if kind == "image":
        img = _flatten_white(img)
        img.thumbnail((1600, 1600), Image.LANCZOS)
        for q in (85, 75, 65):
            out = BytesIO()
            img.save(out, format="JPEG", quality=q, optimize=True)
            data = out.getvalue()
            if len(data) <= IMAGE_MAX:
                break
        else:
            raise ValueError("حجم تصویر بعد از بهینه‌سازی هم بیش از ۲ مگابایت است.")
        final_ext = "jpg"
    else:
        img = img.convert("RGBA")
        for side in (192, 128, 96):
            small = img.copy()
            small.thumbnail((side, side), Image.LANCZOS)
            out = BytesIO()
            small.save(out, format="PNG", optimize=True)
            data = out.getvalue()
            if len(data) <= ICON_MAX:
                break
        else:
            raise ValueError("حجم آیکون بیش از ۱۰۰ کیلوبایت است؛ تصویر ساده‌تری بگذارید.")
        final_ext = "png"

    name = f"{secrets.token_hex(16)}.{final_ext}"
    default_storage.save(f"broadcast/{name}", ContentFile(data))
    return name


def load_assets(broadcast):
    """AssetError اگر فایل انتخاب‌شده‌ی پیام در دسترس نباشد؛ پیام هرگز بی‌صدا بدون تصویر نمی‌رود."""
    icon = None
    if broadcast.icon_name:
        icon = read_asset(broadcast.icon_name, ICON_MAX)
    else:
        default = os.path.join(settings.BASE_DIR, "static", "icons", "icon-192.png")
        if os.path.isfile(default) and os.path.getsize(default) <= ICON_MAX:
            with open(default, "rb") as f:
                icon = ("icon-192.png", f.read(), "image/png")
        else:
            logger.warning("آیکون پیش‌فرض پیام همگانی پیدا نشد یا بزرگ‌تر از ۱۰۰KB است؛ بدون آیکون می‌رود.")
    image = read_asset(broadcast.image_name, IMAGE_MAX) if broadcast.image_name else None
    return {"icon": icon, "image": image}


AUDIENCE_FIELD = {"specialty": "audience_specialties", "role": "audience_roles", "users": "audience_users"}


def parse_audience(post):
    kind = post.get("audience_kind", "")
    if kind == "all_staff":
        return kind, []
    field = AUDIENCE_FIELD.get(kind)
    if not field:
        raise ValueError("نوع مخاطب را انتخاب کنید.")
    raw = post.getlist(field)
    ids = sorted(set(raw) & {"client", "partner"}) if kind == "role" \
        else sorted({int(x) for x in raw if str(x).isdigit()})
    if not ids:
        raise ValueError("مخاطب را انتخاب کنید.")
    return kind, ids


def parse_buttons(post):
    out = []
    for i in (1, 2):
        title, path = (post.get(f"btn{i}_title") or "").strip(), (post.get(f"btn{i}_path") or "").strip()
        if title or path:
            out.append({"title": title, "path": path})
    return out


def sms_parts(n):
    return 1 if n <= 70 else -(-n // 67)


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
    if len(path) > 200 or re.search(r"[\s\\\x00-\x1f]", path):
        return False
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return False
    try:
        resolve(parts.path)
        return True
    except Resolver404:
        return False


def calculate_digest(*, channel, title, body, link_path, ttl_hours, icon_name, image_name,
                     buttons, audience_kind, audience_ids, resolved_user_ids):
    payload = {
        "channel": channel, "title": title, "body": body, "link_path": link_path, "ttl": ttl_hours,
        "icon": icon_name or "", "image": image_name or "", "buttons": buttons or [],
        "kind": audience_kind, "ids": sorted(map(str, audience_ids or [])),
        "users": sorted(resolved_user_ids or []),
    }
    dumped = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def sms_text_length(body, has_link):
    """طول متن نهایی پیامک: متن + (خط جدید + لینک ردیاب) + (خط جدید + امضا). لینک ردیاب = دامنه + /s/ + کد ۵ حرفی."""
    link = (1 + len(settings.SITE_BASE_URL.rstrip("/")) + len("/s/") + 5) if has_link else 0
    return len(body) + link + 1 + len(SIGNATURE)


def validate_content(channel, title, body, ttl_hours, image_name, icon_name, buttons, link_path=""):
    if channel == "push":
        if not title or len(title) > 250:
            raise ValueError("عنوان پوش الزامی و حداکثر ۲۵۰ کاراکتر است.")
        if not body or len(body) > 400:
            raise ValueError("متن پوش الزامی و حداکثر ۴۰۰ کاراکتر است.")
    elif channel == "sms":
        if not body:
            raise ValueError("متن پیامک الزامی است.")
        if sms_text_length(body, bool(link_path)) > 320:
            raise ValueError("متن نهایی پیامک (همراه با لینک و امضا) بیشتر از ۳۲۰ کاراکتر می‌شود.")
    
    if not (1 <= ttl_hours <= 168):
        raise ValueError("مدت ماندگاری باید بین ۱ تا ۱۶۸ ساعت باشد.")
    
    if image_name:
        if not ASSET_RE.match(image_name):
            raise ValueError("تصویر نامعتبر است.")
        if not default_storage.exists(f"broadcast/{image_name}"):
            raise ValueError("تصویر پیدا نشد.")
    if icon_name:
        if not ASSET_RE.match(icon_name):
            raise ValueError("آیکون نامعتبر است.")
        if not default_storage.exists(f"broadcast/{icon_name}"):
            raise ValueError("آیکون پیدا نشد.")
    
    if buttons:
        if not isinstance(buttons, list) or len(buttons) > 2:
            raise ValueError("حداکثر ۲ دکمه مجاز است.")
        for btn in buttons:
            btitle = btn.get("title", "")
            bpath = btn.get("path", "")
            if not btitle or len(btitle) > 20:
                raise ValueError("عنوان دکمه الزامی و حداکثر ۲۰ کاراکتر است.")
            if not bpath or not validate_link(bpath):
                raise ValueError("مسیر دکمه نامعتبر است.")
            base = settings.SITE_BASE_URL.rstrip("/")
            if len(base + bpath) > 80:
                raise ValueError("لینک دکمه با آدرس سایت بیش از ۸۰ کاراکتر می‌شود؛ مسیر کوتاه‌تری بگذارید.")
            if not (base.startswith("https://") or getattr(settings, "BROADCAST_DRY_RUN", False)):
                raise ValueError("آدرس سایت https نیست؛ نجوا دکمه با لینک غیر https را قبول نمی‌کند.")


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


def fail_pending(broadcast_or_id, error):
    """همه‌ی ردیف‌های PENDING یک پیام همگانی را FAILED می‌کند (خطای سراسری)."""
    return Notification.objects.filter(
        broadcast=broadcast_or_id, status=Notification.Status.PENDING,
    ).update(status=Notification.Status.FAILED, error_text=str(error)[:255])


def deliver_one(n, assets):
    """None = ادامه | WAIT = ردیف PENDING می‌ماند و این کانال در این دور قطع می‌شود |
    FAIL_ALL = این ردیف و بقیه‌ی همین پیام FAILED می‌شوند."""
    b = n.broadcast
    if b.is_dry_run:
        _mark(n, SENT[b.channel], error="آزمایشی")
        return None
    if not channel_open(b.channel):
        return WAIT
    return _sms(n, b) if b.channel == "sms" else _push(n, b, assets)


def _sms(n, b):
    phone = n.user.phone_number
    if not phone:
        _mark(n, Notification.Status.FAILED, error="فاقد شماره همراه")
        return None
    text = b.body + (f"\n{n.tracking_url}" if b.link_path and n.tracking_url else "") + f"\n{SIGNATURE}"
    r = SMSService().send_text(mobile=phone, message=text)
    http = r.get("http_status")
    data = r.get("data") if isinstance(r.get("data"), dict) else {}
    code = data.get("status")

    if r.get("success"):                     # status=1 یعنی «پذیرفته شد»، نه «رسید»
        msg_id = r.get("message_id")
        if msg_id is None:
            _mark(n, Notification.Status.FAILED, error="شماره یا متن پیامک نامعتبر است")
        elif msg_id == 0:
            _mark(n, Notification.Status.FAILED, error="شماره در لیست سیاه است")
        else:
            _mark(n, Notification.Status.SMS_SENT, ref=str(msg_id))
        return None
    if http is None or http >= 500 or http == 429 or code in SMS_RATE:
        return WAIT                          # شبکه، خطای سرور یا rate limit: بعداً دوباره
    _mark(n, Notification.Status.FAILED, error=str(r.get("error") or "خطای ارسال"))
    return FAIL_ALL if (code in SMS_GLOBAL or http in (401, 403)) else None


def _push(n, b, assets):
    from utils.models import PushDevice
    tokens = list(PushDevice.objects.filter(user=n.user, is_active=True).values_list("registration_id", flat=True))
    if not tokens:
        _mark(n, Notification.Status.IN_APP)
        return None
    click_url = f"{n.tracking_url}?ch=push" if n.tracking_url else settings.SITE_BASE_URL
    base = settings.SITE_BASE_URL.rstrip("/")
    buttons = [{"title": x.get("title", ""), "url": f"{base}{x.get('path', '/')}"} for x in (b.buttons or [])]

    result = NajvaService().send(
        title=b.title or "فرابخش تهویه", body=b.body, subscriber_tokens=tokens, url=click_url, ttl=b.ttl_hours,
        icon=assets.get("icon"), image=assets.get("image"), buttons=buttons)

    invalid = result.get("invalid_tokens") or []
    if invalid:
        PushDevice.objects.filter(registration_id__in=invalid).update(is_active=False)
    if result.get("success"):
        _mark(n, Notification.Status.PUSH_SENT, ref=str(result.get("request_id") or ""))
        return None
    code = result.get("status_code")
    if code is None:
        if invalid and len(invalid) == len(tokens):
            _mark(n, Notification.Status.IN_APP, error="دستگاه معتبری یافت نشد")
            return None
        return WAIT                          # خطای شبکه یا نجوا پیکربندی نشده
    if code >= 500 or code == 429:
        return WAIT
    _mark(n, Notification.Status.FAILED, error=str(result.get("error") or "خطای ارسال پوش"))
    return FAIL_ALL if code in NAJVA_GLOBAL_HTTP else None


def expire_stale():
    """ردیف تازه‌ی PENDING که از ttl پیامش گذشته (مثلاً کلید یک هفته خاموش بوده) دیگر فرستاده نمی‌شود.
    ردیف‌های «ارسال مجدد» (error_text=RETRY_MARK) معاف‌اند."""
    total = 0
    for b in Broadcast.objects.filter(notifications__status=Notification.Status.PENDING).distinct():
        total += Notification.objects.filter(
            broadcast=b, status=Notification.Status.PENDING, error_text="",
            created_at__lt=now() - timedelta(hours=b.ttl_hours),
        ).update(status=Notification.Status.FAILED, error_text="مهلت ارسال گذشت")
    return total


def _unique_short_codes(n):
    """n کد کوتاه یکتا (bulk_create متد save را صدا نمی‌زند، پس خودمان می‌سازیم)."""
    codes = set()
    while len(codes) < n:
        codes |= {_new_short_code() for _ in range(n - len(codes))}
        taken = set(Notification.objects.filter(short_code__in=codes).values_list("short_code", flat=True))
        codes -= taken
    return list(codes)


def run_process_broadcasts(*, max_seconds=120, heartbeat=None):
    """دسته‌های ۴۰تایی پشت‌سرهم تا صف خالی شود یا زمان تمام شود.
    finalized: ردیفی که از PENDING بیرون رفت (ارسال‌شده، ناموفق، فقط داخل برنامه)
    waiting:   ردیفی که به‌خاطر خطای موقت PENDING ماند (دور بعد دوباره نوبت می‌گیرد)
    more:      کار مانده و فقط زمان تمام شد؛ فراخوان باید دوباره صف کند
    heartbeat: callable بدون آرگومان؛ پیش از هر ردیف صدا زده می‌شود (تمدید قفل)."""
    deadline = time.monotonic() + max_seconds
    stats = {"finalized": 0, "waiting": 0, "expired": expire_stale(), "more": False}
    assets, blocked = {}, set()
    while True:
        open_channels = [c for c in ("push", "sms") if channel_open(c) and c not in blocked]
        rows = list(
            Notification.objects.filter(status=Notification.Status.PENDING, broadcast__isnull=False)
            .filter(Q(broadcast__is_dry_run=True) | Q(broadcast__channel__in=open_channels))
            .order_by("pk").values_list("pk", "broadcast__channel", "broadcast__is_dry_run")[:BATCH])
        if not rows:
            break
        final_in_batch = 0
        for pk, channel, dry in rows:
            if channel in blocked and not dry:
                continue
            if heartbeat:
                heartbeat()
            signal, broadcast_id = None, None
            try:
                with transaction.atomic():
                    n = (Notification.objects.select_for_update(skip_locked=True, of=("self",))
                         .select_related("broadcast", "user")
                         .filter(pk=pk, status=Notification.Status.PENDING).first())
                    if n is None:
                        continue
                    broadcast_id = n.broadcast_id
                    if broadcast_id not in assets:
                        assets[broadcast_id] = load_assets(n.broadcast)
                    signal = deliver_one(n, assets[broadcast_id])
                    if signal == FAIL_ALL:
                        fail_pending(n.broadcast_id, n.error_text or "خطای سراسری")
            except AssetError as e:
                fail_pending(broadcast_id, str(e))
                final_in_batch += 1
                continue
            except Exception:
                logger.exception("broadcast deliver failed %s", pk)
                # نتیجه‌ی ارسال نامعلوم است؛ برای جلوگیری از ارسال تکراری FAILED می‌شود (مدیر دستی «ارسال دوباره» می‌زند)
                Notification.objects.filter(pk=pk, status=Notification.Status.PENDING).update(
                    status=Notification.Status.FAILED, error_text="خطای داخلی")
                final_in_batch += 1
                continue
            if signal == WAIT:
                stats["waiting"] += 1
                blocked.add(channel)
            else:
                final_in_batch += 1
                if signal == FAIL_ALL:
                    blocked.add(channel)
        stats["finalized"] += final_in_batch
        if final_in_batch == 0:            # فقط ردیف‌های منتظر/قفل‌شده مانده؛ حلقه‌ی بی‌نهایت نشود
            break
        if time.monotonic() >= deadline:
            stats["more"] = True
            break
    return stats


def create_broadcast(*, channel, title, body, link_path, icon_name, image_name, ttl_hours,
                     audience_kind, audience_ids, created_by, buttons=None, digest=None, is_test=False):
    if channel == "sms":
        if not channel_open("sms"):
            raise ValueError("پیامک بدون قالب غیرفعال است.")
    elif channel == "push":
        if not channel_open("push"):
            raise ValueError("پوش نوتیفیکیشن غیرفعال است.")

    if link_path and not validate_link(link_path):
        raise ValueError("لینک وارد شده نامعتبر یا خارجی است.")

    buttons = buttons or []
    validate_content(channel, title, body, ttl_hours, image_name, icon_name, buttons, link_path)

    if is_test:
        if channel == "sms" and not created_by.phone_number:
            raise ValueError("برای ارسال آزمایشی، شماره‌ی همراه شما ثبت نشده است.")
        users, audience_kind, audience_ids = [created_by], "users", [created_by.pk]
        audience_label = "آزمایشی به فرستنده"
    else:
        users = resolve_audience(audience_kind, audience_ids, channel)
        audience_label = audience_label_for(audience_kind, audience_ids)
        expected = calculate_digest(
            channel=channel, title=title, body=body, link_path=link_path, ttl_hours=ttl_hours,
            icon_name=icon_name, image_name=image_name, buttons=buttons or [],
            audience_kind=audience_kind, audience_ids=audience_ids,
            resolved_user_ids=[u.id for u in users])
        if digest != expected:
            raise ValueError("محتوای پیام یا گیرندگان تغییر کرده است. دوباره پیش‌نمایش بگیرید.")

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
            created_by=created_by,
            is_test=is_test,
        )

        codes = _unique_short_codes(len(users))
        Notification.objects.bulk_create([
            Notification(
                notification_type=NotificationType.BROADCAST, user=user,
                title=title if channel == "push" else "پیام همگانی", body=body,
                real_target_url=link_path or "/", status=Notification.Status.PENDING,
                broadcast=broadcast, short_code=code,
            ) for user, code in zip(users, codes)
        ])

    return broadcast


def retry_failed(broadcast):
    with transaction.atomic():
        updated = Notification.objects.filter(
            broadcast=broadcast,
            status=Notification.Status.FAILED
        ).update(status=Notification.Status.PENDING, error_text=RETRY_MARK, provider_ref="")
        return updated
