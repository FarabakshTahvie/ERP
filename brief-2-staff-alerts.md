# بریف ۲: پوش برای مدیر و حسابدار (شاخه‌ی `feat/staff-alerts`)

### قواعد ثابت نشست

```
- شاخه: (هر بریف شاخه‌ی خودش؛ مثلاً feat/<نام>، از main تازه). push و merge به main ممنوع.
- git stash و git reset --hard ممنوع.
- پایتون ۳.۱۲ (لوکال، سرور و CI)؛ سینتکس مخصوص ۳.۱۳ به بعد ممنوع.
- هیچ رمز یا کلیدی در فایل، لاگ یا گزارش ننویس.
- تعداد کل تست‌ها کم نشود (مگر حذف/بازنویسی که خود بریف می‌گوید؛ آن را در گزارش با نام بیاور). نام کلاس یا متد تست تکراری ممنوع.
- فقط کار همین گام. کد بریف را عیناً بگذار، «بهتر» نکن. هر جا کد واقعی با بریف نخواند، توقف و گزارش.
- فقط فایل‌هایی که بریف نام برده دست بخورد.
- تصمیم دسترسی فقط با core/capabilities.py. select_for_update همراه select_related فقط با of=("self",).
- در متن UI این کلمه‌ها ممنوع: «اختیاری»، «فعلاً»، «FIFO»، «اسنپ‌شات»، «اتمیک».
- گزارش: تعداد تست قبل و بعد، نام تست‌های جدید/حذف/بازنویسی‌شده، خروجی makemigrations --check --dry-run، نتیجه‌ی هر mutation با نام تست شکست‌خورده (و برگرداندنش)، فهرست فایل‌ها، انحراف‌ها، git log و git branch -a. گزارش جایگزین تست دستی نیست.
- هیچ متنِ آمده از سرور/کاربر با innerHTML، outerHTML، insertAdjacentHTML، document.write یا eval وارد صفحه نشود؛ حتی در کامنت این کلمه‌ها را ننویس. فقط createElement و textContent.
- در تمپلیت فقط کلاس‌های Tailwind v4 و daisyUI v5. کلاس ممنوع: *-bordered، form-control، label-text، rounded-btn، shadow-sm، badge خالی، btn-warning. بج فقط fb-badge. btn-error فقط با btn-soft.
- در تمپلیت `{{ a.b|default:a.c }}` وقتی a ممکن است None باشد ممنوع (آرگومان فیلتر خطا می‌دهد)؛ از {% if a %}...{% else %}—{% endif %} یا فیلتر |person_name استفاده کن.
- کادر عددی تازه: data-money (مبلغ) یا data-decimal (مقدار اعشاری) یا data-digits (کد رقمی)؛ type="number" ممنوع.
- روی عنصری که با JS مخفی/ظاهر می‌شود، کلاس‌های display مثل flex/grid ننویس (فقط hidden)؛ داخلش یک div با flex بگذار.
- فایل JS تازه باید در static/src/input.css با @source ثبت شود و pnpm run build بدون خطا اجرا شود.
- آیکون فقط از sprite.svg؛ آیکون ناموجود را از خودت نساز.
- ممنوع: ساختن کاربر، تکنسین یا هر رکوردی در دیتابیس واقعی (لوکال یا سرور) برای آزمایش. بررسی خودکار فقط با تست‌های Django.
- seed_test_team فقط اگر کاربر صریحاً خواست. هیچ کاربری پاک نشود.
- تست موجود را فقط با «بازنویسی» اصلاح کن، نه حذفِ بی‌دلیل. هر جا بریف sed یا حذف فایل می‌گوید، بعدش grep بزن و خروجی را در گزارش بیاور.
- اگر یک تست قدیمی به‌خاطر همین بریف شکست و در بریف نامش نیامده، تصمیم نگیر: نامش و علت را گزارش کن و فقط اگر علت مستقیم همین تغییر بود با بازنویسی درستش کن.
```

> بعد از بریف ۱ و ۲ هیچ تست تازه‌ای ننوشته‌ایم؛ همه‌ی تست‌ها در بریف ۳ آمده‌اند.

### توضیح ساده
در کد بررسی کردم کدام اتفاق‌های مهم هیچ خبری به مدیر و حسابدار نمی‌دهد. شش مورد پیدا شد که الان فقط در داشبورد دیده می‌شوند. برای هر کدام یک پوش می‌گذاریم.

۱. مشتری پرداخت ثبت کرد و منتظر بررسی است (مدیر و حسابدار). تایید پیش‌فاکتور هم همیشه با ثبت پرداخت می‌آید، پس همین یک پوش آن را هم پوشش می‌دهد.
۲. مشتری پیش‌فاکتور یا مرحله را رد کرد و مرحله معلق شد (مدیر و حسابدار).
۳. مهلت تایید پیش‌فاکتور تمام شد و معلق شد (مدیر و حسابدار). به‌ازای هر پیش‌فاکتور فقط یک‌بار و حتی اگر مشتری حساب ورود نداشته باشد. تسک روزانه‌ی ساعت ۹ از قبل هست و همان را گسترش می‌دهیم.
۴. مرحله‌ای فعال شد ولی مسئول و کاندیدا ندارد (فقط مدیر). الان کسی خبردار نمی‌شود.
۵. مشتری برای ارسال «دریافت نشد» را زد (فقط مدیر).
۶. چکی به ۷ روز مانده به سررسید رسید یا سررسیدش گذشت (مدیر و حسابدار). به‌ازای هر چک یک‌بار و با تسک روزانه‌ی ساعت ۹:۰۵.

از قبل هم، حسابدار با فعال‌شدن مرحله‌ی «صدور پیش‌فاکتور» و «بازبینی نهایی» پوش «کار جدید» می‌گیرد؛ آن‌ها را دست نمی‌زنیم.

برای هر نوع اعلان تازه، سیاست جدا نمی‌سازیم (مثل `TASK_ASSIGNED`)، چون پیش‌فرض `dispatch_notification` بدون سیاست «فقط پوش» است. بنابراین شمار سیاست‌ها و تست `setup_initial_data` عوض نمی‌شود.

### فایل‌ها
`core/capabilities.py`، `notifications/models.py` (+ مایگریشن)، `notifications/services.py`، `finance/services.py`، `finance/deadline.py`، `finance/celery_tasks.py`، `projects/services.py`، `projects/confirmations.py`، `config/settings.py`، `README.md`

### گام ۰ (فقط خواندن)
```
git status --short ; git log --oneline -5 ; python manage.py test    # تعداد را بنویس
grep -n "def notify_users\|def notify_stage_responsible\|def decide_stage_approval\|def set_decision\|def notify_expired_proformas\|def create_customer_payment\|def notify_proforma_expired\|def cheque_soon_q" -r notifications projects finance
grep -n "notify-expired-proformas" config/settings.py
```
اگر نام یا امضای یکی از این‌ها با بریف نخواند، توقف و گزارش.

### گام ۱: `core/capabilities.py`
بعد از تابع `capabilities_for` این تابع را اضافه کن:
```python
def users_with(capability):
    """کاربران فعالِ دارای این قابلیت، به ترتیب شناسه؛ برای اعلان به نقش‌ها (مدیر، حسابدار).
    کارکنان کم‌اند و هر کاربر یک‌بار ارزیابی می‌شود. قابلیت ناشناخته KeyError می‌دهد."""
    try:
        rule = CAPABILITIES[capability]
    except KeyError:
        raise KeyError(f"قابلیت ناشناخته: {capability}")
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    users = (get_user_model().objects.filter(is_active=True)
             .filter(Q(is_superuser=True) | Q(role__in=("manager", "employee"))).order_by("pk"))
    return [u for u in users if rule(_Facts(u))]
```

### گام ۲: انواع اعلان تازه
در `notifications/models.py`، در `NotificationType` بعد از `INVOICE_EXPIRED` اضافه کن:
```python
    PAYMENT_SUBMITTED = "payment_submitted", "پرداخت جدید مشتری"
    APPROVAL_REJECTED = "approval_rejected", "رد مرحله توسط مشتری"
    PROFORMA_SUSPENDED = "proforma_suspended", "تعلیق پیش‌فاکتور (پایان مهلت)"
    STAGE_UNASSIGNED = "stage_unassigned", "مرحله‌ی بدون مسئول"
    SHIPMENT_NOT_RECEIVED = "shipment_not_received", "اقلام دریافت نشد"
    CHEQUE_DUE = "cheque_due", "سررسید چک"
```
سپس `python manage.py makemigrations notifications -n staff_alert_types` را بزن و فایل را کامیت کن. هیچ `NotificationPolicy` برای این‌ها نساز.

در `notifications/services.py` بعد از تابع `notify_users` اضافه کن:
```python
def notify_staff(capability, *, notification_type, title, body, real_target_url="", extra_data=None, exclude=()):
    """اعلان برای همه‌ی کاربران فعالِ دارای یک قابلیت (مثلاً «accounting.access» = مدیر و حسابدار).
    مثل notify_users بعد از commit می‌رود. exclude: شناسه‌ی کسانی که نباید بگیرند (مثل خودِ عامل)."""
    from core.capabilities import users_with
    skip = set(exclude)
    notify_users([u for u in users_with(capability) if u.pk not in skip], notification_type=notification_type,
                 title=title, body=body, real_target_url=real_target_url, extra_data=extra_data)
```

### گام ۳: پرداخت مشتری (`finance/services.py`)
در `create_customer_payment` خط آخر را عوض کن.

قدیم:
```python
    return Payment.objects.create(**kwargs)
```
جدید:
```python
    payment = Payment.objects.create(**kwargs)
    _notify_payment_submitted(payment)
    return payment
```
بعد از تابع `notify_proforma_expired` این سه تابع را اضافه کن:
```python
def _notify_payment_submitted(payment):
    """به مدیر و حسابدار خبر می‌دهد پرداخت مشتری منتظر بررسی است؛ بعد از commit می‌رود (با برگشت تراکنش نمی‌رود)."""
    from django.urls import reverse
    from notifications.models import NotificationType
    from notifications.services import notify_staff
    invoice = payment.invoice
    amount = separate_digits(payment.claimed_amount if payment.claimed_amount is not None else payment.amount)
    notify_staff("payments.review", notification_type=NotificationType.PAYMENT_SUBMITTED,
                 title="پرداخت جدید منتظر بررسی",
                 body=(f"{invoice.billed_party.name} برای پروژه «{invoice.project.name}» پرداخت "
                       f"{payment.get_method_display()} به مبلغ {amount} تومان ثبت کرد؛ منتظر بررسی شماست."),
                 real_target_url=reverse("finance:payment_detail", args=[payment.pk]),
                 extra_data={"invoice_number": invoice.number, "payment_id": payment.pk})


def notify_staff_proforma_expired(invoice):
    """به مدیر و حسابدار می‌گوید این پیش‌فاکتور معلق شده؛ برای هر آخرین روز (valid_until) فقط یک‌بار.
    مستقل از وجود حساب ورود برای مشتری. خروجی: آیا صف شد؟"""
    from django.urls import reverse
    from notifications.models import Notification, NotificationType
    from notifications.services import notify_staff
    if invoice.valid_until is None:
        return False
    url = reverse("projects:proforma_editor", args=[invoice.project_id])
    day = invoice.valid_until.isoformat()
    if Notification.objects.filter(notification_type=NotificationType.PROFORMA_SUSPENDED,
                                   real_target_url=url, extra_data__valid_until=day).exists():
        return False
    notify_staff("accounting.access", notification_type=NotificationType.PROFORMA_SUSPENDED,
                 title="پیش‌فاکتور معلق شد",
                 body=(f"مهلت تایید پیش‌فاکتور {invoice.number} پروژه «{invoice.project.name}» تمام شد. "
                       "قیمت‌ها را اصلاح و مهلت را تمدید کنید."),
                 real_target_url=url, extra_data={"invoice_number": invoice.number, "valid_until": day})
    return True


def notify_cheques_due(today=None):
    """برای هر چکِ تازه‌واردشده به بازه‌ی «تا ۷ روز به سررسید یا گذشته» (cheque_soon_q) یک‌بار به مدیر و حسابدار
    پوش می‌دهد. خروجی: تعداد اعلان صف‌شده."""
    from django.urls import reverse
    from notifications.models import Notification, NotificationType
    from notifications.services import notify_staff
    from utils.jalali import jalali_str
    today = today or timezone.localdate()
    queued = 0
    for p in Payment.objects.filter(cheque_soon_q(today)).select_related("invoice__project"):
        url = reverse("finance:payment_detail", args=[p.pk])
        if Notification.objects.filter(notification_type=NotificationType.CHEQUE_DUE, real_target_url=url).exists():
            continue
        late = p.cheque_due_date < today
        notify_staff("payments.review", notification_type=NotificationType.CHEQUE_DUE,
                     title="سررسید چک گذشته است" if late else "سررسید چک نزدیک است",
                     body=(f"چک پروژه «{p.invoice.project.name}» (فاکتور {p.invoice.number}) به مبلغ "
                           f"{separate_digits(p.amount)} تومان؛ سررسید {jalali_str(p.cheque_due_date, fmt='%Y/%m/%d')}."),
                     real_target_url=url, extra_data={"payment_id": p.pk})
        queued += 1
    return queued
```

### گام ۴: تسک‌های روزانه
در `finance/deadline.py` تابع `notify_expired_proformas` را عوض کن.

قدیم:
```python
    from .services import notify_proforma_expired
    today = today or timezone.localdate()
    invoices = list(suspended_invoices_qs(today).select_related("billed_party", "project"))
    return sum(1 for inv in invoices if notify_proforma_expired(inv))
```
جدید:
```python
    from .services import notify_proforma_expired, notify_staff_proforma_expired
    today = today or timezone.localdate()
    invoices = list(suspended_invoices_qs(today).select_related("billed_party", "project"))
    queued = 0
    for inv in invoices:
        queued += 1 if notify_proforma_expired(inv) else 0
        notify_staff_proforma_expired(inv)   # حتی اگر مشتری حساب ورود ندارد، حسابدار باید بداند
    return queued
```
در docstring همان تابع بعد از «پیامک» اضافه کن: «به مدیر و حسابدار هم پوش می‌رود».

به انتهای `finance/celery_tasks.py` اضافه کن:
```python
@shared_task(name="finance.notify_cheques_due", ignore_result=True, soft_time_limit=270, time_limit=300)
def notify_cheques_due_task():
    from .services import notify_cheques_due
    logger.info("notify_cheques_due: %s queued", notify_cheques_due())
    return None
```
در `config/settings.py` داخل `CELERY_BEAT_SCHEDULE` زیر ردیف `"notify-expired-proformas"` اضافه کن:
```python
    "notify-cheques-due": {"task": "finance.notify_cheques_due", "schedule": crontab(hour=9, minute=5)},
```

### گام ۵: رد مرحله (`projects/services.py`)
در `decide_stage_approval`، شاخه‌ی رد را عوض کن.

قدیم:
```python
    elif decision == StageApproval.Decision.REJECTED:
        advance_stage(stage, actor=actor, new_status=ProjectStage.Status.REJECTED, comment=comment)

    return approval
```
جدید:
```python
    elif decision == StageApproval.Decision.REJECTED:
        advance_stage(stage, actor=actor, new_status=ProjectStage.Status.REJECTED, comment=comment)
        _notify_approval_rejected(stage, approval, comment)

    return approval
```
درست بالای `def decide_stage_approval` اضافه کن:
```python
def _notify_approval_rejected(stage, approval, comment):
    """رد مشتری به مدیر و حسابدار خبر می‌دهد (بعد از commit). اگر مرحله معلق شد، همین را می‌گوید."""
    from django.urls import reverse
    from notifications.models import NotificationType
    from notifications.services import notify_staff
    project = stage.project
    suspended = stage.status == ProjectStage.Status.SUSPENDED
    url = (reverse("projects:proforma_editor", args=[project.pk]) if stage.step_template.requires_payment_selection
           else reverse("projects:staff_project_overview", args=[project.pk]))
    reason = " ".join((comment or "").split())[:150]
    body = f"{approval.sent_to_party.name} مرحله «{stage.client_label or stage.title}» پروژه «{project.name}» را رد کرد"
    body += "؛ مرحله معلق شد" if suspended else ""
    body += f": {reason}" if reason else "."
    notify_staff("accounting.access", notification_type=NotificationType.APPROVAL_REJECTED,
                 title="مشتری مرحله را رد کرد", body=body, real_target_url=url,
                 extra_data={"project_id": project.pk})
```

### گام ۶: مرحله‌ی بدون مسئول (`projects/services.py`)
در `notify_stage_responsible` بعد از بلوک `if stage.assigned_to_id: ... else: ...` که `users, pool` را می‌سازد، این را اضافه کن:
```python
    users = [u for u in users if u.is_active]
    if not users:   # کسی نیست که خبردار شود؛ مدیر باید ارجاع بدهد
        from django.urls import reverse
        from notifications.services import notify_staff
        notify_staff("stages.assign", notification_type=NotificationType.STAGE_UNASSIGNED,
                     title="مرحله بدون مسئول",
                     body=(f"مرحله «{stage.title}» از پروژه «{stage.project.name}» فعال شد ولی مسئول یا "
                           "کاندیدایی ندارد؛ ارجاعش دهید."),
                     real_target_url=reverse("dashboard:assign_stage", args=[stage.pk]))
        return
```
بقیه‌ی تابع (ساخت `body` و `notify_users`) دست‌نخورده می‌ماند.

### گام ۷: «دریافت نشد» (`projects/confirmations.py`)
در `set_decision`، بعد از `conf.save(update_fields=[...])` و قبل از `return conf`:
```python
    if decision == D.NOT_RECEIVED:
        _notify_not_received(project, stage)
```
و بالای `set_decision` اضافه کن:
```python
def _notify_not_received(project, stage):
    """مشتری «دریافت نشد» زد؛ مدیر باید پیگیری کند (بعد از commit؛ تکرار همان پاسخ دوباره خبر نمی‌دهد)."""
    from django.urls import reverse
    from notifications.models import NotificationType
    from notifications.services import notify_staff
    notify_staff("dashboard.manager", notification_type=NotificationType.SHIPMENT_NOT_RECEIVED,
                 title="مشتری اقلام را دریافت نکرد",
                 body=f"مشتریِ پروژه «{project.name}» برای مرحله «{stage.title}» «دریافت نشد» را زد؛ با او تماس بگیرید.",
                 real_target_url=reverse("projects:staff_project_overview", args=[project.pk]))
```
(تکرار همان پاسخ از قبل با `if conf.decision == decision: return conf` برمی‌گردد.)

### گام ۸: README
در بخش Celery جمله‌ی «همچنین Celery beat روزانه ساعت ۹ صبح پیامک مهلت‌گذشته پیش‌فاکتورها را ارسال می‌کند.» را این کن:
«همچنین Celery beat روزانه ساعت ۹ صبح پیامک مهلت‌گذشته پیش‌فاکتورها را به مشتری و پوش «پیش‌فاکتور معلق شد» را به مدیر و حسابدار می‌فرستد؛ ساعت ۹:۰۵ هم برای چک‌های نزدیک به سررسید پوش می‌رود (یک‌بار برای هر چک).»

### گام ۹: بررسی
```
python manage.py makemigrations --check --dry-run
python manage.py test
```
هر تست قدیمی که شکست خورد: نام و علت را گزارش کن و فقط اگر علت مستقیم همین بریف بود با بازنویسی درستش کن. بعد از مرج، روی سرور `update.sh` خودش worker و beat را ری‌استارت می‌کند.

### گزارش خواسته‌شده
مثل بریف ۱، به‌علاوه نام تست‌های قدیمی که احتمالاً شکستند.

### تست دستی کاربر
۱. حسابدار در «مرکز اعلان» دکمه‌ی «فعال‌سازی اعلان» را بزند تا دستگاهش ثبت شود.
۲. با `client_test`: تایید پیش‌فاکتور با کارت به کارت. حسابدار و مدیر هر کدام یک پوش «پرداخت جدید منتظر بررسی» بگیرند و فقط یکی (نه دو تا).
۳. رد پیش‌فاکتور: پوش «مشتری مرحله را رد کرد … مرحله معلق شد».
۴. در `shell` لوکال مهلت یک پیش‌فاکتور را به دیروز ببر و `from finance.deadline import notify_expired_proformas; notify_expired_proformas()` را بزن. پوش بیاید؛ بار دوم نیاید.
۵. یک چک با سررسید ۳ روز بعد ثبت کن و `from finance.services import notify_cheques_due; notify_cheques_due()` را بزن.

### پرسش غیرمسدود
حسابدار دقیقاً کدام اتفاق را می‌خواست؟ این شش مورد را به او نشان بده. اگر مورد دیگری خواست یا مواردی زیاد بود، می‌گویی.

### موکول
گروه‌بندی چند پیش‌فاکتور معلق در یک پوش (الان هر کدام یک پوش است)، یادآوری «ماه قبل هنوز بسته نشده»، پوش برای مدیر هنگام لغو پروژه.
