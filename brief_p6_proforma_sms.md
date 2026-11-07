# بریف ۶ — دکمه‌ی دستی «ارسال پیامک» در صفحه‌ی فاکتور

> ترتیب اجرا: بعد از merge بریف ۵ (ترتیب کلی: ۶ ← ۷ ← ۸ ← ۹). شاخه: `feat/proforma-sms` (از `main` تازه). بلوک «قواعد ثابت» را خودت اول نشست به دستیار بده؛ اینجا تکرار نشده.
>
> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. اگر تست موجودی به‌خاطر این تغییر شکست، نام و علتش را گزارش کن و فقط با بازنویسی درستش کن.
>
> **تصمیم پایه:** متن پیامک همان قالب «پیش‌فاکتور شما ثبت شد» است، چون قالب «ویرایش شد» هنوز نیست. پیامک نام کاربری (موبایل) و لینک صفحه‌ی فاکتور را دارد. رمز هرگز نوشته نمی‌شود و به‌جایش «رمز فعلی شما» می‌آید؛ مشتری با «ورود با کد پیامکی» وارد می‌شود. اگر طرف‌حساب حساب نداشته باشد، خود دکمه حسابش را می‌سازد و رمز تازه در پیامک می‌رود. دکمه همیشه هست و فقط دستی کار می‌کند؛ بعد از ویرایش هیچ پیامک خودکاری نمی‌رود.

**شاخه:** `feat/proforma-sms`

**توضیح ساده:** روی صفحه‌ی فاکتور یک کارت «پیامک پیش‌فاکتور» می‌آید. حسابدار با یک دکمه پیامک را برای طرف‌حساب می‌فرستد. کنار دکمه وضعیت آخرین پیامک دیده می‌شود (ارسال شد، ناموفق، هنوز نرفته). پیامک خودکار بعد از ویرایش نداریم؛ هر وقت حسابدار لازم دید خودش می‌فرستد. پیامکِ ناموفق را می‌شود فوراً دوباره فرستاد، اما پیامکِ موفق را فقط بعد از یک دقیقه.

**فایل‌ها:** `finance/services.py`، `projects/views.py`، `templates/projects/partials/proforma_body.html`.

### گام ۰ (فقط خواندن)
```
git status --short && git log --oneline -5 && git branch -a
grep -n "def ensure_billed_party_account\|def build_invoice_lines" finance/services.py
grep -n "from finance.services import build_invoice_lines\|\"can_extend\"\|مهلت تمدید شد" projects/views.py
grep -n "{% if can_issue %}" templates/projects/partials/proforma_body.html
```
اگر `build_invoice_lines` یا `can_extend` نبود (بریف ۵ merge نشده)، توقف و گزارش.

### گام ۱ — `finance/services.py` (آخر فایل اضافه شود)
```python
SMS_RESEND_SECONDS = 60


def last_invoice_sms(invoice):
    """آخرین اعلان «پیش‌فاکتور شما ثبت شد» برای همین فاکتور (خودکار یا دستی)؛ None اگر هیچ‌وقت نرفته."""
    from notifications.models import Notification, NotificationType
    return (Notification.objects
            .filter(notification_type=NotificationType.INVOICE_ISSUED,
                    real_target_url=f"/portal/invoices/{invoice.uuid}/")
            .order_by("-created_at", "-pk").first())


@transaction.atomic
def resend_invoice_sms(*, invoice, actor):
    """ارسال دستیِ پیامک پیش‌فاکتور. هیچ رمزی عوض نمی‌شود: اگر حساب از قبل بود پیامک «رمز فعلی شما» را می‌نویسد؛
    فقط وقتی حساب همین لحظه ساخته شد رمز تازه‌اش در پیامک می‌رود. پیامکِ موفق تا یک دقیقه دوباره نمی‌رود."""
    from core.capabilities import can
    from notifications.models import Notification, NotificationType
    from notifications.services import notify_users
    from .accounting import log_event
    from .models import AccountingEvent
    if not can(actor, "pricing.edit"):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند پیامک پیش‌فاکتور را بفرستد.")
    invoice = (Invoice.objects.select_for_update(of=("self",))
               .select_related("billed_party", "project").get(pk=invoice.pk))
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("این فاکتور لغو شده است.")
    last = last_invoice_sms(invoice)
    if (last is not None and last.status != Notification.Status.FAILED
            and last.created_at >= timezone.now() - timedelta(seconds=SMS_RESEND_SECONDS)):
        raise ValueError("همین پیامک لحظاتی پیش فرستاده شد؛ یک دقیقه صبر کنید.")
    user, raw_password = ensure_billed_party_account(invoice)
    if user is None:
        raise ValueError("این شماره‌ی موبایل برای حساب دیگری (مثلاً پرسنل) ثبت شده؛ پیامک نرفت.")
    if not user.is_active:
        raise ValueError("حساب ورود این طرف‌حساب غیرفعال است.")
    if not user.phone_number:
        raise ValueError("طرف‌حساب شماره‌ی موبایل ندارد.")
    notify_users([user], notification_type=NotificationType.INVOICE_ISSUED, title="پیش‌فاکتور شما صادر شد",
                 body=f"پیش‌فاکتور شماره {invoice.number} صادر شد.",
                 real_target_url=f"/portal/invoices/{invoice.uuid}/",
                 extra_data={"invoice_number": invoice.number, "username": user.username,
                             "password": raw_password or ""})
    log_event(kind=AccountingEvent.Kind.INVOICE_LINE, project=invoice.project, actor=actor,
              text=f"ارسال دستی پیامک پیش‌فاکتور {invoice.number} به {user.phone_number}")
```

### گام ۲ — `projects/views.py` (سه جایگزینی)
۱. import:

قدیم: `from finance.services import build_invoice_lines`
جدید: `from finance.services import build_invoice_lines, last_invoice_sms, resend_invoice_sms`

۲. در `_proforma_context`:

قدیم:
```python
        "can_extend": bool(invoice and deadline_open(invoice)),
```
جدید:
```python
        "can_extend": bool(invoice and deadline_open(invoice)),
        "can_sms": bool(invoice and invoice.status != "cancelled"),
        "last_sms": last_invoice_sms(invoice) if invoice else None,
```

۳. در `proforma_editor` بعد از شاخه‌ی `extend`:

قدیم:
```python
                messages.success(request, "مهلت تمدید شد؛ پیش‌فاکتور دوباره برای مشتری فعال است.")
                return redirect("projects:proforma_editor", project.id)
```
جدید:
```python
                messages.success(request, "مهلت تمدید شد؛ پیش‌فاکتور دوباره برای مشتری فعال است.")
                return redirect("projects:proforma_editor", project.id)
            elif action == "resend_sms":
                invoice = getattr(project, "invoice", None)
                if invoice is None:
                    raise ValueError("پیش‌فاکتور هنوز صادر نشده است.")
                resend_invoice_sms(invoice=invoice, actor=request.user)
                messages.success(request, "درخواست ارسال ثبت شد؛ نتیجه را در بخش «پیامک پیش‌فاکتور» ببینید.")
                return redirect("projects:proforma_editor", project.id)
```

### گام ۳ — `templates/projects/partials/proforma_body.html`
درست **قبل از** خط `    {% if can_issue %}` این کارت را بگذار:
```html
    {% if invoice and can_sms %}
    <form method="post" data-fb-once class="fb-card fb-pad flex flex-col gap-3">
        {% csrf_token %}
        <input type="hidden" name="action" value="resend_sms">
        <div class="flex items-center justify-between gap-2 flex-wrap">
            <h2 class="fb-section-title">پیامک پیش‌فاکتور</h2>
            {% if last_sms %}
            <span class="fb-badge {% if last_sms.status == 'failed' %}fb-badge-error{% elif last_sms.status == 'sms_sent' or last_sms.status == 'seen' %}fb-badge-success{% else %}fb-badge-warning{% endif %}">
                {{ last_sms.get_status_display }} — <span class="font-technical">{{ last_sms.created_at|to_jalali:"%Y/%m/%d %H:%M" }}</span>
            </span>
            {% else %}
            <span class="fb-badge fb-badge-warning">هنوز پیامکی نرفته</span>
            {% endif %}
        </div>
        <p class="fb-hint">بعد از ویرایش، پیامک خودکار نمی‌رود؛ هر وقت لازم بود خودتان بفرستید. متن همان «پیش‌فاکتور شما ثبت شد» است با نام کاربری (شماره‌ی موبایل) و لینک صفحه‌ی فاکتور. رمز در پیامک نیست؛ مشتری با «ورود با کد پیامکی» وارد می‌شود. اگر طرف‌حساب حساب ورود نداشته باشد، همین دکمه حسابش را می‌سازد و رمزش را در پیامک می‌فرستد.</p>
        <button type="submit" class="btn btn-soft btn-sm self-start">{% icon "send" "w-4 h-4" %} ارسال پیامک به طرف‌حساب</button>
    </form>
    {% endif %}
```

### گام ۴ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود (نه `finance/tests_invoice_sms.py`). کل تست‌های موجود را اجرا کن. چون `finance/services.py` هسته‌ی مالی است، `TEST_ON_POSTGRES=True python manage.py test finance projects` را هم یک بار اجرا کن و نتیجه را بیاور. این‌ها را هم بزن و خروجی را بیاور:
```
python manage.py check
python manage.py makemigrations --check --dry-run
grep -rn "resend_invoice_sms\|last_invoice_sms" --include=*.py .
grep -n "resend_sms" projects/views.py templates/projects/partials/proforma_body.html
```
JS و CSS عوض نشده، پس `pnpm run build` لازم نیست.

### گزارش
طبق قواعد ثابت، به‌علاوه:
- نتیجه‌ی تست روی Postgres.
- خروجی `grep -rn "resend_invoice_sms\|last_invoice_sms" --include=*.py .`

### تست دستی (کاربر)
- با `tech_accountant_1` روی پیش‌فاکتور صادرشده دکمه‌ی «ارسال پیامک به طرف‌حساب» را بزن.
- روی لوکال پیامک واقعی نمی‌رود. وضعیت «ناموفق» یا «در انتظار» طبیعی است.
- اگر `setup_notification_policies` اجرا نشده باشد پیامک نمی‌رود و اعلان «فقط داخل برنامه» می‌شود.
- دو بار پشت‌سرهم بزن. بار دوم باید پیام «یک دقیقه صبر کنید» بیاید.
- پیامکِ ناموفق را بلافاصله دوباره بفرست؛ باید برود.
- با کاربری که دسترسی ویرایش قیمت ندارد، فرم POST کار نکند.
- روی فاکتور لغوشده کارت پیامک نباشد.
- حالت روشن، تاریک و موبایل را ببین.

**پرسش غیرمسدود:** اگر دکمه‌ی پیامک پیش‌فاکتورِ لغوشده هم لازم است بگو؛ الان برای فاکتور لغوشده نیست.
**موکول:** قالب «پیش‌فاکتور شما ویرایش شد» در sms.ir. با آن، همین دکمه متن بهتری می‌گیرد.
