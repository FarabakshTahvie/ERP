# بریف ۱ — مهلت تایید و تعلیق پیش‌فاکتور (بک‌اند)

> ترتیب اجرا: اول از همه. شاخه: `feat/proforma-deadline` (از `main` تازه). بلوک «قواعد ثابت» را خودت اول نشست به دستیار بده؛ اینجا تکرار نشده.
>
> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. اگر تست موجودی به‌خاطر این تغییر شکست، طبق قواعد ثابت نام و علتش را گزارش کن.

**شاخه:** `feat/proforma-deadline`

**توضیح ساده:** به فاکتور یک فیلد «آخرین روز تایید» اضافه می‌کنیم. اگر مشتری تا آن روز تایید نکند، پیش‌فاکتور تعلیق می‌شود: مشتری نمی‌تواند تایید یا پرداخت ثبت کند. حسابدار و مدیر با «تمدید مهلت» آن را برمی‌گردانند. این بریف UI ندارد.

**فایل‌ها:** `finance/models.py`، `finance/deadline.py` (تازه)، `finance/services.py`، `projects/proforma.py`، `projects/views.py`.

### گام ۰ (فقط خواندن)
```
git status --short && git log --oneline -5 && git branch -a
python manage.py test 2>&1 | tail -4
grep -rn "valid_until" --include=*.py . | grep -v migrations
grep -n "def create_customer_payment" finance/services.py
grep -n "def issue_proforma" projects/proforma.py
```

### گام ۱ — مدل
در `finance/models.py` کلاس `Invoice` زیر `due_date` اضافه کن:
```python
    valid_until = models.DateField(null=True, blank=True, verbose_name="آخرین روز تایید پیش‌فاکتور")
```
بعد `python manage.py makemigrations finance -n invoice_valid_until`. فاکتور قدیمی `None` می‌گیرد و هیچ‌وقت منقضی نمی‌شود.

### گام ۲ — فایل تازه `finance/deadline.py` (عیناً)
```python
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.capabilities import can

DEFAULT_DAYS = 1
MAX_DAYS = 30
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_deadline_days(raw):
    """خالی یا None = پیش‌فرض (۱ روز). غیر از عدد صحیح ۱ تا ۳۰ = ValueError فارسی."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    if not text:
        return DEFAULT_DAYS
    if not text.isdigit() or not (1 <= int(text) <= MAX_DAYS):
        raise ValueError("مهلت تایید باید عددی صحیح بین ۱ تا ۳۰ روز باشد.")
    return int(text)


def last_day_for(days, today=None):
    """آخرین روز تایید = امروز + days. مهلت تا ساعت ۲۴ همان روز است، نه ۲۴ ساعت بعد از صدور."""
    return (today or timezone.localdate()) + timedelta(days=days)


def deadline_open(invoice):
    """مهلت فقط وقتی معنی دارد که مشتری هنوز تایید نکرده و پولی ثبت نشده (همان شرط باز بودن قیمت‌ها)."""
    from projects.services import project_prices_editable
    from .models import Invoice
    if invoice.status == Invoice.Status.CANCELLED or invoice.document_type != Invoice.DocumentType.PROFORMA:
        return False
    return project_prices_editable(invoice.project)


def deadline_state(invoice, today=None):
    """'none' | 'active' | 'expired'"""
    if invoice.valid_until is None or not deadline_open(invoice):
        return "none"
    return "expired" if (today or timezone.localdate()) > invoice.valid_until else "active"


def office_phone_text():
    return settings.COMPANY_CONTACT["office_phone"]["display"]


def expired_message(invoice, today=None):
    if deadline_state(invoice, today) != "expired":
        return ""
    return ("مهلت تایید این پیش‌فاکتور تمام شده است. برای تایید و به‌روزشدن قیمت‌ها با دفتر تماس بگیرید: "
            + office_phone_text())


def assert_not_expired(invoice):
    message = expired_message(invoice)
    if message:
        raise ValueError(message)


@transaction.atomic
def extend_deadline(*, invoice, days_raw, reason, actor):
    """تمدید مهلت (= خروج از تعلیق). فقط مدیر یا حسابدار؛ دلیل اجباری؛ ردپا در AccountingEvent."""
    from utils.jalali import jalali_str
    from .accounting import log_event
    from .models import AccountingEvent, Invoice
    if not can(actor, "pricing.edit"):
        raise ValueError("فقط حسابدار یا مدیر می‌تواند مهلت را تمدید کند.")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("دلیل تمدید را بنویسید.")
    days = parse_deadline_days(days_raw)
    invoice = Invoice.objects.select_for_update(of=("self",)).select_related("project").get(pk=invoice.pk)
    if not deadline_open(invoice):
        raise ValueError("این پیش‌فاکتور مهلت ندارد؛ یا مشتری تایید کرده، یا پولی ثبت شده، یا لغو شده است.")
    old, new = invoice.valid_until, last_day_for(days)
    invoice.valid_until = new
    invoice.save(update_fields=["valid_until", "updated_at"])
    show = lambda d: jalali_str(d, fmt="%Y/%m/%d") if d else "ندارد"
    log_event(kind=AccountingEvent.Kind.INVOICE_LINE, project=invoice.project, actor=actor,
              text=f"مهلت تایید پیش‌فاکتور {invoice.number}: {show(old)} ← {show(new)} — {reason}")
    return invoice
```

### گام ۳ — بستن پرداخت مشتری (`finance/services.py`)
در `create_customer_payment`:

قدیم:
```python
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("این فاکتور لغو شده است و پرداخت جدید ثبت نمی‌شود.")
```
جدید (دو خط بعد از `raise` اضافه شود):
```python
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("این فاکتور لغو شده است و پرداخت جدید ثبت نمی‌شود.")
    from .deadline import assert_not_expired
    assert_not_expired(invoice)
```
تایید مرحله‌ی ۳ توسط مشتری هم همین‌جا بسته می‌شود، چون پرداخت را از همین تابع می‌سازد. «رد» دست‌نخورده می‌ماند.

### گام ۴ — صدور با مهلت (`projects/proforma.py`، تابع `issue_proforma`)
۱. امضا:
```python
def issue_proforma(*, project, actor, send_sms=False, deadline_days=None):
```
۲. قدیم:
```python
    from finance.services import generate_invoice_for_project, ensure_billed_party_account, notify_invoice_issued
    if not can_edit_pricing(actor, project):
```
جدید:
```python
    from finance.services import generate_invoice_for_project, ensure_billed_party_account, notify_invoice_issued
    from finance.deadline import last_day_for, parse_deadline_days
    days = parse_deadline_days(deadline_days)   # اول از همه؛ مهلت نامعتبر هیچ‌چیز نمی‌سازد
    if not can_edit_pricing(actor, project):
```
۳. قدیم:
```python
    invoice.status = Invoice.Status.SENT
    invoice.save(update_fields=["status"])
```
جدید:
```python
    invoice.status = Invoice.Status.SENT
    invoice.valid_until = last_day_for(days)
    invoice.save(update_fields=["status", "valid_until"])
```

### گام ۵ — ویو (`projects/views.py`، `proforma_editor`)
قدیم:
```python
                invoice, conflict = issue_proforma(
                    project=project, actor=request.user, send_sms=request.POST.get("send_sms") == "on")
```
جدید:
```python
                invoice, conflict = issue_proforma(
                    project=project, actor=request.user, send_sms=request.POST.get("send_sms") == "on",
                    deadline_days=request.POST.get("deadline_days"))
```

### گام ۶ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود (نه `finance/tests_deadline.py` و نه `projects/tests_proforma_deadline.py`). کل تست‌های موجود را اجرا کن. خروجی این‌ها را در گزارش بیاور:
```
python manage.py makemigrations --check --dry-run
python manage.py check
grep -rn "assert_not_expired\|deadline_days\|valid_until" --include=*.py . | grep -v migrations
```


**پرسش غیرمسدود:** حداکثر مهلت ۳۰ روز مناسب است؟
**موکول:** نمایش مهلت به مشتری (بریف ۲)، فرم تمدید برای حسابدار (بریف ۵).
