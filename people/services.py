import re
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginHistory, User
from core.capabilities import can
from core.models import Party, Specialty
from finance.models import AccountingEvent, Payment
from inventory.models import StockMovement
from projects.models import PartRequest, Project, ProjectFile, ProjectStage, StageEvent
from projects.services import parse_fee
from utils.jalali import jalali_str
from utils.utils import generate_random_code, is_valid_national_code

ONLINE_MINUTES = 5
FEED_DAYS = (7, 30, 90)
_RE_PHONE = re.compile(r"^09\d{9}$")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

PAGE_LABELS = {
    "home": "صفحه اصلی",
    "dashboard:overview": "داشبورد مدیر",
    "dashboard:stages": "مراحل فعال و ارجاع",
    "dashboard:suspended": "پروژه‌های معلق",
    "dashboard:held_detail": "پرونده‌ی پروژه‌ی معلق",
    "projects:staff_project_overview": "نمای پروژه",
    "projects:my_task_detail": "جزئیات کار",
    "projects:proforma_editor": "ویرایشگر پیش‌فاکتور",
    "projects:final_review": "بازبینی نهایی",
    "projects:new_project_form": "ثبت پروژه",
    "projects:project_edit": "ویرایش پروژه",
    "projects:part_request_detail": "درخواست قطعه",
    "finance:payments_review": "پرداخت‌ها",
    "finance:payment_detail": "بررسی پرداخت",
    "finance:accounting_overview": "مرکز حسابداری",
    "finance:accounting_project": "پرونده‌ی مالی",
    "finance:accounting_periods": "قفل ماه‌ها",
    "finance:accounting_customers": "مرکز مشتریان",
    "inventory:stock_movement_new": "ثبت مصرف یا تعدیل",
    "inventory:purchase_new": "ثبت خرید",
    "inventory:bulk_opening": "ورود گروهی موجودی",
    "inventory:bulk_reconciliation": "انبارگردانی",
    "people:staff": "افراد",
    "tasks:list": "وظایف",
    "tasks:detail": "جزئیات وظیفه",
    "tasks:edit": "ویرایش وظیفه",
    "accounts:change_password": "تغییر رمز عبور",
    "notifications:center": "اعلان‌ها",
    "notifications:broadcast_form": "ارسال پیام",
    "notifications:broadcast_history": "فهرست پیام‌های همگانی",
    "notifications:broadcast_detail": "جزئیات پیام همگانی",
    "messenger:inbox": "پیام‌رسان",
    "messenger:chat": "پیام‌رسان",
}


def page_label(view_name):
    return PAGE_LABELS.get(view_name or "", "صفحه‌ی دیگر")


def seen_text(presence, now=None):
    if presence is None:
        return "هنوز دیده نشده"
    now = now or timezone.now()
    if (now - presence.last_seen).total_seconds() < ONLINE_MINUTES * 60:
        return "همین حالا"
    return jalali_str(presence.last_seen, fmt="%Y/%m/%d %H:%M")


def _guard(actor, user):
    if not can(actor, "people.edit"):
        raise ValueError("فقط مدیر می‌تواند اطلاعات افراد را تغییر دهد.")
    if user.is_superuser and not actor.is_superuser:
        raise ValueError("فقط مدیر ارشد می‌تواند حساب مدیر ارشد را تغییر دهد.")


@transaction.atomic
def update_user_profile(*, user, actor, first_name, last_name, phone_number, email, national_code, specialty_ids=None):
    """specialty_ids=None یعنی تخصص‌ها را دست نزن. نقش از اینجا عوض نمی‌شود (فقط پنل مدیریت)."""
    _guard(actor, user)
    user = User.objects.select_for_update().get(pk=user.pk)
    first, last = (first_name or "").strip(), (last_name or "").strip()
    if not (first or last):
        raise ValueError("نام را بنویسید.")
    if len(first) > 150 or len(last) > 150:
        raise ValueError("نام یا نام خانوادگی بیش از حد طولانی است.")
    phone = (phone_number or "").strip().translate(_DIGITS)
    if phone:
        if not _RE_PHONE.match(phone):
            raise ValueError("شماره موبایل معتبر نیست (باید ۱۱ رقم بوده و با 09 شروع شود).")
        if User.objects.filter(phone_number=phone).exclude(pk=user.pk).exists():
            raise ValueError("این شماره‌ی موبایل برای کاربر دیگری ثبت شده است.")
    mail = (email or "").strip()
    if mail:
        try:
            validate_email(mail)
        except ValidationError:
            raise ValueError("ایمیل معتبر نیست.")
    code = (national_code or "").strip().translate(_DIGITS)
    if code:
        if not is_valid_national_code(code):
            raise ValueError("کد ملی معتبر نیست.")
        if User.objects.filter(national_code=code).exclude(pk=user.pk).exists():
            raise ValueError("این کد ملی برای کاربر دیگری ثبت شده است.")

    old_phone = user.phone_number
    fields = ["first_name", "last_name", "phone_number", "email", "national_code"]
    if phone and old_phone and user.username == old_phone and phone != old_phone:
        if User.objects.filter(username=phone).exclude(pk=user.pk).exists():
            raise ValueError("نام کاربری مربوط به این شماره قبلاً ثبت شده است.")
        user.username = phone   # نام کاربری ورود همان شماره‌ی موبایل بوده؛ هم‌گام می‌شود
        fields.append("username")

    reason = "ویرایش اطلاعات توسط مدیر"
    specs = None
    if user.role == User.Role.EMPLOYEE and specialty_ids is not None:
        ids = [int(x) for x in specialty_ids if str(x).isdigit()]
        specs = list(Specialty.objects.filter(pk__in=ids))
        reason += " — تخصص‌ها: " + ("، ".join(sorted(s.name for s in specs)) or "هیچ")

    user.first_name, user.last_name = first, last
    user.phone_number, user.email, user.national_code = phone or None, mail, code or None
    user._change_reason = reason
    user.save(update_fields=fields)
    if specs is not None:
        user.specialties.set(specs)
    return user


@transaction.atomic
def reset_user_password(*, user, actor):
    """رمز موقت می‌سازد و برمی‌گرداند. فقط همین یک‌بار؛ در هیچ‌جا ذخیره یا لاگ نمی‌شود."""
    _guard(actor, user)
    if user.pk == actor.pk:
        raise ValueError("رمز خودتان را از «تغییر رمز عبور» عوض کنید.")
    user = User.objects.select_for_update().get(pk=user.pk)
    raw = generate_random_code(length=10, digits_only=False)
    user.set_password(raw)
    user.must_change_password = True
    user._change_reason = "بازنشانی رمز توسط مدیر"
    user.save(update_fields=["password", "must_change_password"])
    return raw


@transaction.atomic
def set_user_active(*, user, active, actor, reason):
    """خروجی: تعداد مرحله‌ی در حال انجامی که هنوز به او سپرده شده (برای هشدار)."""
    _guard(actor, user)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("ثبت دلیل اجباری است.")
    if not active and user.pk == actor.pk:
        raise ValueError("نمی‌توانید حساب خودتان را غیرفعال کنید.")
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.is_active == active:
        raise ValueError("وضعیت حساب همین است.")
    user.is_active = active
    user._change_reason = f"{'فعال' if active else 'غیرفعال'}سازی توسط مدیر: {reason}"
    user.save(update_fields=["is_active"])
    if active:
        return 0
    from projects.services import _assign_stage_responsible, notify_stage_responsible
    stages = list(ProjectStage.objects.select_for_update(of=("self",)).select_related("step_template", "project")
                  .filter(assigned_to=user, status=ProjectStage.Status.IN_PROGRESS,
                          project__status=Project.Status.IN_PROGRESS))
    for st in stages:
        st.assigned_to = None
        st.save(update_fields=["assigned_to", "updated_at"])
        st.candidate_users.clear()
        _assign_stage_responsible(st)            # استخر هم‌تخصص‌های فعال (کاربر الان غیرفعال است)
        if st.assigned_to_id and not st.assigned_to.is_active:
            st.assigned_to = None                # قالب مسئول ثابتی داشت که همین کاربر بود
        st.save()
        StageEvent.objects.create(stage=st, actor=actor, from_status=st.status, to_status=st.status,
                                  comment=f"مسئول قبلی غیرفعال شد؛ مرحله به چرخه برگشت: {reason}")
        notify_stage_responsible(st)
    return len(stages)


@transaction.atomic
def update_party_profile(*, party, actor, name, brand_name, phone_number, secondary_phone, email,
                         description, credit_limit_raw):
    """نقش‌ها و کد ملی/ثبت از اینجا عوض نمی‌شوند (فاکتور و حساب ورود به آن‌ها وابسته است)."""
    if not can(actor, "people.edit"):
        raise ValueError("فقط مدیر می‌تواند اطلاعات طرف‌حساب را تغییر دهد.")
    party = Party.objects.select_for_update().get(pk=party.pk)
    name = (name or "").strip()
    if not name:
        raise ValueError("نام طرف‌حساب را بنویسید.")
    phone = (phone_number or "").strip().translate(_DIGITS)
    if phone and Party.objects.filter(phone_number=phone).exclude(pk=party.pk).exists():
        raise ValueError("طرف‌حساب دیگری با این شماره وجود دارد.")
    mail = (email or "").strip()
    if mail:
        try:
            validate_email(mail)
        except ValidationError:
            raise ValueError("ایمیل معتبر نیست.")
    party.name, party.brand_name = name[:255], (brand_name or "").strip()[:255]
    party.phone_number = phone[:20]
    party.secondary_phone = (secondary_phone or "").strip().translate(_DIGITS)[:20]
    party.email, party.description = mail, (description or "").strip()
    party.credit_limit = parse_fee(credit_limit_raw, label="سقف اعتبار")
    party._change_reason = "ویرایش توسط مدیر"
    party.save()
    return party


def user_work_summary(person):
    live = (ProjectStage.objects.filter(assigned_to=person, status=ProjectStage.Status.IN_PROGRESS,
                                        project__status=Project.Status.IN_PROGRESS).select_related("project"))
    return {
        "active_stages": list(live[:20]),
        "done_count": ProjectStage.objects.filter(completed_by=person).count(),
        "created_projects": list(Project.objects.filter(created_by=person).order_by("-created_at")[:10]),
    }


def account_history(person, limit=15):
    """فقط تغییرهای مدیریتی (دارای دلیل)؛ ورودها که last_login را عوض می‌کنند نیامده."""
    qs = (person.history.select_related("history_user")
          .exclude(history_change_reason__isnull=True).exclude(history_change_reason="")
          .order_by("-history_date")[:limit])
    return [{"at": h.history_date, "reason": h.history_change_reason,
             "who": (h.history_user.get_full_name() or h.history_user.username) if h.history_user else "سیستم"}
            for h in qs]


def activity_feed(user, *, days=30, limit=150):
    """فید یکپارچه از رکوردهای موجود؛ جدیدترین اول."""
    since = timezone.now() - timedelta(days=days)
    rows = []

    def add(at, kind, text, url=None):
        if at:
            rows.append({"at": at, "kind": kind, "text": text, "url": url})

    names = {n for n in (user.username, user.phone_number) if n}
    logins = LoginHistory.objects.filter(created_at__gte=since).filter(
        Q(user=user) | Q(user__isnull=True, username_attempted__in=names)).order_by("-created_at")[:limit]
    for h in logins:
        ok = h.result == LoginHistory.Result.SUCCESS
        add(h.created_at, "ورود" if ok else "ورود ناموفق",
            " · ".join(x for x in (h.browser, h.os, h.ip_address) if x))

    events = StageEvent.objects.filter(actor=user, created_at__gte=since).select_related("stage__project")
    for e in events.order_by("-created_at")[:limit]:
        add(e.created_at, "رویداد مرحله", f"{e.stage.project.name} — {e.stage.title}: {(e.comment or '')[:120]}",
            reverse("projects:staff_project_overview", args=[e.stage.project_id]))

    files = ProjectFile.objects.filter(uploaded_by=user, created_at__gte=since).select_related("stage__project")
    for f in files.order_by("-created_at")[:limit]:
        add(f.created_at, "فایل", f"{f.display_name} — {f.stage.project.name}",
            reverse("projects:staff_project_overview", args=[f.stage.project_id]))

    moves = StockMovement.objects.filter(created_by=user, created_at__gte=since).select_related("item")
    for m in moves.order_by("-created_at")[:limit]:
        add(m.created_at, "حرکت انبار", f"{m.get_movement_type_display()}: {m.item.name} × {m.qty.normalize():f}")

    pays = Payment.objects.filter(approved_by=user, approved_at__gte=since).select_related("invoice")
    for p in pays.order_by("-approved_at")[:limit]:
        add(p.approved_at, "بررسی پرداخت", f"{p.get_status_display()} — {p.invoice.number}",
            reverse("finance:payment_detail", args=[p.id]))

    acc = AccountingEvent.objects.filter(actor=user, created_at__gte=since)
    for a in acc.order_by("-created_at")[:limit]:
        add(a.created_at, "حسابداری", a.text,
            reverse("finance:accounting_project", args=[a.project_id]) if a.project_id else None)

    parts = PartRequest.objects.filter(requested_by=user, requested_at__gte=since).select_related("item", "project")
    for r in parts.order_by("-requested_at")[:limit]:
        add(r.requested_at, "درخواست قطعه", f"{r.item.name} — {r.project.name}",
            reverse("projects:part_request_detail", args=[r.id]))

    for p in Project.objects.filter(created_by=user, created_at__gte=since).order_by("-created_at")[:limit]:
        add(p.created_at, "ثبت پروژه", p.name, reverse("projects:staff_project_overview", args=[p.id]))

    rows.sort(key=lambda r: r["at"], reverse=True)
    return rows[:limit]
