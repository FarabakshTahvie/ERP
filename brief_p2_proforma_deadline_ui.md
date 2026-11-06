# بریف ۲ — پیام مهلت برای مشتری، متن ۳۰٪ اعتباری، ترتیب پرداخت‌ها

> ترتیب اجرا: بعد از merge بریف ۱. شاخه: `feat/proforma-deadline-ui` (از `main` بعد از merge بریف ۱). بلوک «قواعد ثابت» را خودت اول نشست به دستیار بده؛ اینجا تکرار نشده.
>
> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. اگر تست موجودی به‌خاطر این تغییر شکست، طبق قواعد ثابت نام و علتش را گزارش کن.

**شاخه:** `feat/proforma-deadline-ui`

**توضیح ساده:** مشتری در صفحه‌ی فاکتور و صفحه‌ی تایید می‌بیند «مهلت تا چه روزی» و یک دکمه‌ی اقدام دارد. وقتی منقضی شد، پیام «با دفتر تماس بگیرید» می‌آید. هنگام انتخاب «اعتباری» یادآوری ۳۰ درصد می‌آید. در تایید پرداخت‌ها، قدیمی‌ترینِ منتظر تایید بالا می‌آید.

**فایل‌ها:** `finance/deadline.py`، `finance/views.py`، `projects/views.py`، `templates/finance/portal_invoice.html`، `templates/projects/portal_stage_approval.html`، `templates/finance/partials/payment_fields.html`، `templates/finance/payments_review.html`.

### گام ۰
```
git log --oneline -5 && ls finance/deadline.py
grep -n "deadline" finance/views.py projects/views.py
```

### گام ۱ — `finance/deadline.py` (آخر فایل اضافه شود)
```python
def deadline_info(invoice, today=None):
    """برای نمایش در قالب‌ها؛ مشتری و حسابدار هر دو از همین می‌خوانند."""
    today = today or timezone.localdate()
    state = deadline_state(invoice, today)
    return {
        "state": state,
        "last_day": invoice.valid_until if state != "none" else None,
        "days_left": (invoice.valid_until - today).days if state == "active" else None,
        "phone": office_phone_text(),
        "phone_tel": settings.COMPANY_CONTACT["office_phone"]["tel"],
    }
```

### گام ۲ — `finance/views.py`
بالای فایل: `from .deadline import deadline_info, expired_message`

در `invoice_detail` دیکشنری context را این‌طور کن:
```python
    return render(request, "finance/portal_invoice.html", {
        "invoice": invoice, "pending_approval": pending_approval, "payments": payments, "is_owner": is_owner,
        "deadline": deadline_info(invoice),
    })
```
در `add_payment`، بعد از بلوک `if invoice.remaining_amount <= 0:` و قبل از `if request.method == "POST":` این را بگذار:
```python
    expired = expired_message(invoice)
    if expired:
        messages.error(request, expired)
        return redirect("finance:portal_invoice_detail", invoice.uuid)
```

### گام ۳ — `projects/views.py` (`portal_stage_approval`)
بعد از `from core.capabilities import can` اولِ تابع:
```python
    from finance.deadline import deadline_info
```
در `render_page` قدیم:
```python
        ctx = {"approval": approval, "stage": stage, "invoice": invoice,
               "needs_payment": needs_payment, "readonly": not is_owner}
```
جدید:
```python
        ctx = {"approval": approval, "stage": stage, "invoice": invoice,
               "needs_payment": needs_payment, "readonly": not is_owner,
               "deadline": deadline_info(invoice) if invoice else None}
```

### گام ۴ — `templates/finance/portal_invoice.html`
۱. درست بعد از بلوک `{% if invoice.status == 'cancelled' %} ... {% endif %}` (آلرت لغو) اضافه کن:
```html
        {% if deadline.state == 'active' %}
        <div role="alert" class="alert alert-soft alert-warning">
            {% icon "clock" "w-4 h-4 shrink-0" %}
            <div class="text-sm flex flex-col gap-1">
                <span class="font-semibold">مهلت تایید تا ساعت ۲۴ روز <span class="font-technical">{{ deadline.last_day|to_jalali:"%Y/%m/%d" }}</span></span>
                <span class="text-xs">اگر تا آن زمان تایید نشود، پیش‌فاکتور منقضی می‌شود و قیمت‌ها باید دوباره بررسی شوند. لطفاً همین حالا تایید و پرداخت را انجام دهید.</span>
            </div>
        </div>
        {% elif deadline.state == 'expired' %}
        <div role="alert" class="alert alert-soft alert-error">
            {% icon "alert-circle" "w-4 h-4 shrink-0" %}
            <div class="text-sm flex flex-col gap-2">
                <span>مهلت تایید این پیش‌فاکتور تمام شده است. قیمت‌ها ممکن است تغییر کرده باشد؛ برای تایید با دفتر تماس بگیرید.</span>
                <a href="tel:{{ deadline.phone_tel }}" class="btn btn-soft btn-sm self-start">{% icon "phone" "w-4 h-4" %} تماس با دفتر: <span dir="ltr" class="font-technical">{{ deadline.phone }}</span></a>
            </div>
        </div>
        {% endif %}
```
۲. قدیم: `{% icon "check-circle" "w-4 h-4" %} تایید و پرداخت` ← جدید: `{% icon "check-circle" "w-4 h-4" %} {% if deadline.state == 'expired' %}مشاهده و پاسخ{% else %}تایید و پرداخت{% endif %}`

۳. قدیم: `{% elif invoice.remaining_amount > 0 and invoice.status != 'cancelled' %}` ← جدید: `{% elif invoice.remaining_amount > 0 and invoice.status != 'cancelled' and deadline.state != 'expired' %}`

### گام ۵ — `templates/projects/portal_stage_approval.html`
در شاخه‌ی فرم (`{% else %}` بعد از `readonly`):
۱. درست بعد از `{% csrf_token %}` داخل فرم همان بلوک آلرت گام ۴ را بگذار (دو شاخه‌ی active و expired). متن expired را اینجا کوتاه کن: «مهلت تایید تمام شده است؛ فقط می‌توانید پاسخ را رد کنید یا با دفتر تماس بگیرید.»
۲. قدیم: `{% if needs_payment %}` (بالای include فیلدهای پرداخت) ← جدید: `{% if needs_payment and deadline.state != 'expired' %}`
۳. دکمه‌ی تایید را بپیچ:
```html
            {% if deadline.state != 'expired' %}<button type="submit" name="action" value="approve" class="btn btn-primary flex-1">تایید</button>{% endif %}
```

### گام ۶ — متن ۳۰٪ (`payment_fields.html`)
۱. زیر div سلکتِ `payment-method` (قبل از `<div id="bank-cards-box" ...>`):
```html
    <div id="credit-hint" class="hidden">
        <div role="alert" class="alert alert-soft alert-warning">
            {% icon "alert-triangle" "w-4 h-4 shrink-0" %}
            <span class="text-xs">لطفاً قبل از استفاده از این گزینه، حداقل ۳۰ درصد مبلغ را با سایر روش‌ها پرداخت کنید.</span>
        </div>
    </div>
```
۲. در تابع `fbTogglePaymentFields` بعد از خط `el('cheque-fields').classList.toggle('hidden', !isCheque);` اضافه کن:
```js
    el('credit-hint').classList.toggle('hidden', !isCredit);
```

### گام ۷ — ترتیب پرداخت‌ها (`finance/views.py`، `_payments_table_context`)
در import بالا `DateTimeField` و `F` را به `from django.db.models import ...` اضافه کن. قدیم:
```python
    qs = _visible_payments(request.user).annotate(
        review_rank=Case(When(status=Payment.Status.PENDING, then=0), default=1, output_field=IntegerField()),
        cheque_soon=Case(When(cheque_soon_q(), then=Value(True)), default=Value(False), output_field=BooleanField()),
    ).order_by("review_rank", "-created_at")
```
جدید:
```python
    qs = _visible_payments(request.user).annotate(
        review_rank=Case(When(status=Payment.Status.PENDING, then=0), default=1, output_field=IntegerField()),
        pending_at=Case(When(status=Payment.Status.PENDING, then=F("created_at")), output_field=DateTimeField()),
        cheque_soon=Case(When(cheque_soon_q(), then=Value(True)), default=Value(False), output_field=BooleanField()),
    ).order_by("review_rank", "pending_at", "-created_at")
```
در `payments_review.html` متن زیرعنوان را به این تغییر بده: «همه‌ی پرداخت‌های ثبت‌شده؛ منتظر تایید بالاتر از بقیه است و قدیمی‌ترین اول می‌آید. برای بررسی روی هر ردیف بزنید.»

### گام ۸ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود (نه `finance/tests_deadline_ui.py`). کل تست‌های موجود را اجرا کن؛ `python manage.py check` و `pnpm run build` هم اجرا شود. این grepها را بزن و خروجی را بیاور:
```
grep -n "deadline" templates/finance/portal_invoice.html templates/projects/portal_stage_approval.html
grep -n "credit-hint" templates/finance/partials/payment_fields.html
grep -n "pending_at" finance/views.py
```

### تست دستی (کاربر)
با `client_test` روی پروژه‌ی تازه، فاکتور را تا مرحله‌ی تایید ببر و `valid_until` را از `shell` دستی نه؛ با صبر یا با تمدید بریف ۵ امتحان کن. حالت روشن و تاریک و موبایل را ببین. «اعتباری» را انتخاب کن و جمله‌ی ۳۰٪ را ببین.
- در حالت فعال: آلرت «مهلت تایید تا ساعت ۲۴ روز ...» دیده شود و فیلدهای پرداخت و دکمه‌ی تایید باشند.
- در حالت منقضی: آلرت قرمز با دکمه‌ی تماس با دفتر؛ فیلدهای پرداخت و دکمه‌ی تایید نباشند، «رد» کار کند؛ ثبت پرداخت از صفحه‌ی فاکتور به همین پیام برگردد.
- در تایید پرداخت‌ها: منتظر تایید بالاتر از بقیه و قدیمی‌ترین اول؛ بقیه جدیدترین اول.

**پرسش غیرمسدود:** در تعلیق، دکمه‌ی «تماس با دفتر» کافی است یا فرم «درخواست تماس» هم لازم است؟
