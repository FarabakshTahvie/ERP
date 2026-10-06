import os
import hashlib
import logging
from django.conf import settings
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.urls import resolve, Resolver404
from django.contrib.auth import get_user_model

from accounts.models import User
from utils.sms import SMSService
from utils.push_notification import NajvaService
from utils.image_utils import optimize_receipt_image
from notifications.models import Broadcast, Notification, NotificationType

logger = logging.getLogger(__name__)

# حداکثر ظرفیت‌ها طبق بریف
MAX_PUSH_RECIPIENTS = 500
MAX_SMS_RECIPIENTS = 200

def resolve_audience(kind, ids, channel):
    """
    بررسی و استخراج لیست کاربران فعال و بدون تکرار بر اساس نوع مخاطب.
    - all_staff: مدیر و تکنسین فعال.
    - specialty: تکنسین‌های فعال با تخصص‌های مشخص‌شده در ids.
    - role: کاربران فعال با نقش‌های مشخص‌شده در ids (در صورت کارفرما/شریک تجاری باید party مشخص باشد).
    - users: شناسه‌های کاربر مشخص‌شده در ids.
    
    حذف‌شده‌ها:
    - برای پیامک: کاربران فاقد شماره همراه حذف می‌شوند.
    - برای پوش: همه کاربران فعال انتخاب می‌شوند (بدون دستگاه‌ها وضعیت به IN_APP می‌رود).
    """
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
        other_roles = [r for r in ids if r not in ["client", "partner"]]
        if other_roles:
            query |= Q(role__in=other_roles)
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
    """
    اعتبارسنجی لینک داخلی.
    باید خالی باشد یا با / شروع شود و با // شروع نشود و توسط سیستم مسیردهی جنگو (resolve) شناخته شود.
    """
    if not path:
        return True
    if not path.startswith("/") or path.startswith("//"):
        return False
    try:
        resolve(path)
        return True
    except Resolver404:
        return False


def calculate_digest(body, audience_kind, audience_ids, image_name, channel):
    """
    محاسبه هش یکتا (sha256 hex) برای تایید دومرحله‌ای بر اساس داده‌های ارسال پیام.
    """
    payload_str = f"{body}|{audience_kind}|{sorted(audience_ids or [])}|{image_name or ''}|{channel}"
    return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()


def handle_broadcast_image(uploaded_file):
    """
    ذخیره و بهینه‌سازی تصویر آپلود شده تا ۲ مگابایت.
    از نام تصادفی ۳۲ هگز و فقط در پوشه media/broadcast/ استفاده می‌شود.
    """
    if uploaded_file.size > 2 * 1024 * 1024:
        raise ValueError("حجم فایل نباید بیش از ۲ مگابایت باشد.")
    
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise ValueError("فرمت تصویر نامعتبر است. فقط JPG, PNG, WEBP مجاز هستند.")
    
    optimized_file, changed = optimize_receipt_image(uploaded_file)
    
    random_hex = hashlib.md5(os.urandom(32)).hexdigest()
    final_ext = ".webp" if ext == ".webp" else ".jpg"
    new_filename = f"{random_hex}{final_ext}"
    
    save_path = os.path.join("broadcast", new_filename)
    path = default_storage.save(save_path, ContentFile(optimized_file.read()))
    return os.path.basename(path)


def create_broadcast(*, channel, title, body, link_path, icon_name, image_name, ttl_hours, audience_kind, audience_ids, audience_label, created_by, is_test=False, digest=None):
    """
    ساخت پیام همگانی و ردیف‌های اطلاع‌رسانی مربوطه به شکل اتمیک.
    """
    if channel == "sms":
        if not getattr(settings, "SMS_FREE_TEXT_ENABLED", False) and not getattr(settings, "BROADCAST_DRY_RUN", False):
            raise ValueError("پیامک بدون قالب غیرفعال است.")
    elif channel == "push":
        if not getattr(settings, "NAJVA_ENABLED", False) and not getattr(settings, "BROADCAST_DRY_RUN", False):
            raise ValueError("پوش نوتیفیکیشن غیرفعال است.")

    if link_path and not validate_link(link_path):
        raise ValueError("لینک وارد شده نامعتبر یا خارجی است.")

    if not is_test:
        expected_digest = calculate_digest(body, audience_kind, audience_ids, image_name, channel)
        if digest != expected_digest:
            raise ValueError("محتوای پیام یا گیرندگان تغییر کرده است. لطفاً ابتدا پیش‌نمایش را بررسی کنید.")

    if is_test:
        users = [created_by]
    else:
        users = resolve_audience(audience_kind, audience_ids, channel)

    if channel == "sms" and len(users) > MAX_SMS_RECIPIENTS:
        raise ValueError(f"تعداد گیرندگان پیامک بیش از حد مجاز است (حداکثر {MAX_SMS_RECIPIENTS} کاربر).")
    if channel == "push" and len(users) > MAX_PUSH_RECIPIENTS:
        raise ValueError(f"تعداد گیرندگان پوش بیش از حد مجاز است (حداکثر {MAX_PUSH_RECIPIENTS} کاربر).")

    skipped_count = 0
    if not is_test:
        full_audience = resolve_audience(audience_kind, audience_ids, "push")
        if channel == "sms":
            skipped_count = len(full_audience) - len(users)

    is_dry_run = getattr(settings, "BROADCAST_DRY_RUN", False)

    with transaction.atomic():
        broadcast = Broadcast.objects.create(
            channel=channel,
            title=title,
            body=body,
            link_path=link_path,
            icon_name=icon_name,
            image_name=image_name,
            ttl_hours=ttl_hours,
            audience_kind=audience_kind,
            audience_ids=audience_ids or [],
            audience_label=audience_label if not is_test else f"تست توسط {created_by.get_full_name() or created_by.username}",
            recipients_count=len(users),
            skipped_count=skipped_count,
            is_test=is_test,
            is_dry_run=is_dry_run,
            created_by=created_by
        )

        notifications = []
        for user in users:
            notifications.append(Notification(
                notification_type=NotificationType.BROADCAST,
                user=user,
                title=title or "پیام همگانی",
                body=body,
                real_target_url=link_path,
                status=Notification.Status.PENDING,
                broadcast=broadcast
            ))
        if notifications:
            Notification.objects.bulk_create(notifications)

    return broadcast


def retry_failed(broadcast):
    """
    برگرداندن پیام‌های ناموفق (FAILED) یک Broadcast به وضعیت PENDING جهت ارسال مجدد.
    """
    with transaction.atomic():
        updated = Notification.objects.filter(
            broadcast=broadcast,
            status=Notification.Status.FAILED
        ).update(status=Notification.Status.PENDING, error_text="")
        return updated
