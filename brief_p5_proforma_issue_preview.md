# بریف ۵ — پیش‌نمایش قبل از صدور، بنر مهلت و تمدید

> ترتیب اجرا: بعد از merge بریف ۴ (و ۱ تا ۳). شاخه: `feat/proforma-issue` (از `main` تازه). بلوک «قواعد ثابت» را خودت اول نشست به دستیار بده؛ اینجا تکرار نشده.
>
> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. اگر تست موجودی به‌خاطر این تغییر شکست، نام و علتش را گزارش کن و فقط با بازنویسی درستش کن.

**شاخه:** `feat/proforma-issue`

**توضیح ساده:** حسابدار پیش از صدور، همان چیزی را که مشتری می‌بیند در همین صفحه می‌بیند: ردیف‌ها، جمع و پیام مهلت. بعد «تایید و صدور» را می‌زند. بعد از صدور، بالای صفحه وضعیت مهلت (فعال یا معلق) دیده می‌شود. حسابدار یا مدیر در همان‌جا مهلت را تمدید می‌کند، یعنی از تعلیق بیرون می‌آورد. ویرایش ردیف‌ها در حالت تعلیق باز می‌ماند، چون بریف ۳ آن را نبسته است.

**فایل‌ها:** `finance/services.py`، `projects/views.py`، `templates/projects/proforma_editor.html`، `templates/projects/partials/proforma_body.html`، `templates/projects/partials/proforma_preview.html` (تازه).

### گام ۰
```
git status --short && git log --oneline -5 && git branch -a
grep -n "def extend_deadline\|def deadline_info\|def deadline_open\|def parse_deadline_days" finance/deadline.py
grep -n "def _rebuild_lines\|def _make_line" finance/services.py
grep -rn "_rebuild_lines" --include=*.py .
```
اگر `finance/deadline.py` یا `deadline_info` نبود (بریف ۱ و ۲ merge نشده)، توقف و گزارش.

### گام ۱ — جداکردن ساخت ردیف‌ها (`finance/services.py`)
ساخت ردیف از ذخیره جدا می‌شود تا پیش‌نمایش دقیقاً همان ردیف‌های فاکتور واقعی را نشان بدهد. رفتار `_rebuild_lines` عوض نمی‌شود (الگوی ۷).

قدیم:
```python
def _rebuild_lines(invoice, project):
    lines = []
    for ps in project.services.select_related("service").prefetch_related("materials"):
```
جدید:
```python
def build_invoice_lines(project, invoice=None):
    """ردیف‌های فاکتور از روی پروژه، ذخیره‌نشده. invoice=None یعنی فقط پیش‌نمایش."""
    lines = []
    for ps in project.services.select_related("service").prefetch_related("materials"):
```
قدیم (انتهای همان تابع):
```python
        lines.append(_make_line(invoice, InvoiceLine.LineType.EXTRA, "هزینه‌های مازاد (شامل عوامل اجرایی بیرونی)", 1, extra_total))

    InvoiceLine.objects.bulk_create(lines)
    recalculate_invoice_total(invoice)
```
جدید:
```python
        lines.append(_make_line(invoice, InvoiceLine.LineType.EXTRA, "هزینه‌های مازاد (شامل عوامل اجرایی بیرونی)", 1, extra_total))
    return lines


def _rebuild_lines(invoice, project):
    InvoiceLine.objects.bulk_create(build_invoice_lines(project, invoice))
    recalculate_invoice_total(invoice)
```

### گام ۲ — ویو (`projects/views.py`)
importهای تازه (کنار بقیه‌ی importهای بالای فایل):
```python
from finance.deadline import deadline_info, deadline_open, extend_deadline, last_day_for, parse_deadline_days
from finance.services import build_invoice_lines
```
در `_proforma_context`، داخل دیکشنری بازگشتی این دو کلید را اضافه کن:
```python
        "deadline": deadline_info(invoice) if invoice else None,
        "can_extend": bool(invoice and deadline_open(invoice)),
```
تابع `proforma_editor` را با این جایگزین کن (`proforma_body` دست‌نخورده):
```python
def _lines_total(project):
    return int(sum((l.total for l in build_invoice_lines(project)), Decimal("0")))


@login_required
def proforma_editor(request, project_id):
    project = get_object_or_404(Project.objects.select_related("location", "partner", "owner"), pk=project_id)
    if not can_edit_pricing(request.user, project):
        raise Http404
    preview = None
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "preview":
                if not _proforma_context(request, project)["can_issue"]:
                    raise ValueError("الان نمی‌شود پیش‌فاکتور صادر کرد؛ مرحله‌ی صدور فعال نیست یا قبلاً صادر شده.")
                if not project.services.exists():
                    raise ValueError("حداقل یک خدمت باید ثبت شود.")
                days = parse_deadline_days(request.POST.get("deadline_days"))
                lines = build_invoice_lines(project)
                preview = {"lines": lines, "total": sum((l.total for l in lines), Decimal("0")),
                           "days": days, "last_day": last_day_for(days),
                           "send_sms": request.POST.get("send_sms") == "on",
                           "seen_total": _lines_total(project)}
            elif action == "issue":
                if request.POST.get("seen_total") != str(_lines_total(project)):
                    messages.warning(request, "مبلغ پیش‌فاکتور بعد از پیش‌نمایش تغییر کرده یا پیش‌نمایش دیده نشده است. پیش‌نمایش را دوباره بگیرید.")
                    return redirect("projects:proforma_editor", project.id)
                invoice, conflict = issue_proforma(
                    project=project, actor=request.user, send_sms=request.POST.get("send_sms") == "on",
                    deadline_days=request.POST.get("deadline_days"))
                messages.success(request, f"پیش‌فاکتور {invoice.number} صادر شد.")
                if conflict:
                    messages.warning(request, "این شماره موبایل قبلاً برای یک حساب دیگر (مثلاً پرسنل) ثبت شده؛ حساب ورود خودکار ساخته نشد. از پنل ادمین دستی حساب بسازید.")
                return redirect("projects:proforma_editor", project.id)
            elif action == "extend":
                invoice = getattr(project, "invoice", None)
                if invoice is None:
                    raise ValueError("پیش‌فاکتور هنوز صادر نشده است.")
                extend_deadline(invoice=invoice, days_raw=request.POST.get("days"),
                                reason=request.POST.get("reason"), actor=request.user)
                messages.success(request, "مهلت تمدید شد؛ پیش‌فاکتور دوباره برای مشتری فعال است.")
                return redirect("projects:proforma_editor", project.id)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:proforma_editor", project.id)
        if preview is None:
            return redirect("projects:proforma_editor", project.id)
    ctx = _proforma_context(request, project)
    ctx["preview"] = preview
    return render(request, "projects/proforma_editor.html", ctx)
```
(`last_day_for` همین‌جا همراه بقیه از `finance.deadline` import شده است؛ import محلی لازم نیست.)

### گام ۳ — تمپلیت‌ها
**۱. `proforma_body.html`:** فرم صدور موقت (از `{% if can_issue %}` تا `{% endif %}` مربوطه) را با این جایگزین کن. فرم حالا پیش‌نمایش می‌گیرد:
```html
    {% if can_issue %}
    <form method="post" data-fb-once class="fb-card fb-pad flex flex-col gap-3">
        {% csrf_token %}
        <input type="hidden" name="action" value="preview">
        <h2 class="fb-section-title">صدور پیش‌فاکتور</h2>
        <div class="fb-field max-w-xs">
            <label class="fb-label" for="pf-deadline">مهلت تایید مشتری (روز)</label>
            <input type="text" id="pf-deadline" name="deadline_days" value="1" data-digits maxlength="2" dir="ltr" inputmode="numeric" autocomplete="off" class="input w-full font-technical">
            <span class="fb-hint">مشتری تا ساعت ۲۴ روز آخر مهلت دارد؛ مثلاً امروز با مهلت ۱ روز یعنی تا ساعت ۲۴ فردا.</span>
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" name="send_sms" class="checkbox checkbox-sm" checked>
            <span class="text-sm">پیامک پیش‌فاکتور همراه با نام کاربری و رمز عبور برای طرف‌حساب ارسال شود</span>
        </label>
        <button type="submit" class="btn btn-primary btn-sm self-start">پیش‌نمایش پیش‌فاکتور مشتری</button>
    </form>
    {% endif %}
```
همین فایل: درست بعد از بلوک `{% if not editable %}...{% endif %}` (بالای صفحه) این بنر و فرم تمدید را اضافه کن:
```html
    {% if invoice and deadline %}
    {% if deadline.state == 'active' %}
    <div role="alert" class="alert alert-soft alert-info">
        {% icon "clock" "w-4 h-4 shrink-0" %}
        <span class="text-sm">مهلت تایید مشتری تا ساعت ۲۴ روز <span class="font-technical">{{ deadline.last_day|to_jalali:"%Y/%m/%d" }}</span>؛ {% if deadline.days_left == 0 %}امروز آخرین روز است.{% else %}<span class="font-technical">{{ deadline.days_left|fa_digits }}</span> روز دیگر.{% endif %}</span>
    </div>
    {% elif deadline.state == 'expired' %}
    <div role="alert" class="alert alert-soft alert-error">
        {% icon "alert-circle" "w-4 h-4 shrink-0" %}
        <span class="text-sm">مهلت تایید تمام شده و پیش‌فاکتور برای مشتری معلق است؛ مشتری نمی‌تواند تایید یا پرداخت کند و باید با دفتر تماس بگیرد. قیمت‌ها را اصلاح کنید و بعد مهلت را تمدید کنید.</span>
    </div>
    {% endif %}
    {% if can_extend %}
    <form method="post" data-fb-once class="fb-card fb-pad flex flex-col gap-3">
        {% csrf_token %}
        <input type="hidden" name="action" value="extend">
        <h2 class="fb-section-title">{% if deadline.state == 'expired' %}تمدید مهلت و خروج از تعلیق{% else %}تمدید مهلت{% endif %}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div class="fb-field">
                <label class="fb-label" for="pf-extend-days">چند روز از امروز</label>
                <input type="text" id="pf-extend-days" name="days" value="1" data-digits maxlength="2" dir="ltr" inputmode="numeric" autocomplete="off" class="input w-full font-technical">
            </div>
            <div class="fb-field sm:col-span-2">
                <label class="fb-label" for="pf-extend-reason">دلیل (اجباری)</label>
                <input type="text" id="pf-extend-reason" name="reason" required maxlength="300" class="input w-full">
            </div>
        </div>
        <button type="submit" class="btn btn-primary btn-sm self-start">ثبت تمدید</button>
    </form>
    {% endif %}
    {% endif %}
```
**۲. `templates/projects/partials/proforma_preview.html` (تازه):**
```html
{% load custom_tags %}
<section id="proforma-preview" class="fb-card fb-pad flex flex-col gap-4">
    <div>
        <h2 class="fb-section-title">پیش‌نمایش آنچه مشتری می‌بیند</h2>
        <p class="fb-hint">هنوز صادر نشده است. اگر همه‌چیز درست است «تایید و صدور» را بزنید؛ برای اصلاح به ردیف‌های پایین برگردید.</p>
    </div>
    <div role="alert" class="alert alert-soft alert-warning">
        {% icon "clock" "w-4 h-4 shrink-0" %}
        <div class="text-sm flex flex-col gap-1">
            <span class="font-semibold">مهلت تایید تا ساعت ۲۴ روز <span class="font-technical">{{ preview.last_day|to_jalali:"%Y/%m/%d" }}</span></span>
            <span class="text-xs">اگر تا آن زمان تایید نشود، پیش‌فاکتور منقضی می‌شود و قیمت‌ها باید دوباره بررسی شوند. لطفاً همین حالا تایید و پرداخت را انجام دهید.</span>
        </div>
    </div>
    <div class="overflow-x-auto">
        <table class="table table-sm">
            <thead>
                <tr class="text-xs fb-muted">
                    <th class="w-12 text-center font-medium">ردیف</th><th class="font-medium">شرح</th>
                    <th class="text-center font-medium">مقدار</th><th class="text-center font-medium">مبلغ واحد (تومان)</th>
                    <th class="text-center font-medium">جمع کل (تومان)</th>
                </tr>
            </thead>
            <tbody>
                {% for l in preview.lines %}
                <tr>
                    <td class="text-center font-technical">{{ forloop.counter|fa_digits }}</td>
                    <td class="font-medium">{{ l.title }}</td>
                    <td class="text-center font-technical">{{ l.qty|floatformat:"-2"|fa_digits }}</td>
                    <td class="text-center font-technical">{{ l.unit_price|intcomma_fa }}</td>
                    <td class="text-center font-technical font-semibold">{{ l.total|intcomma_fa }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="flex justify-end">
        <div class="w-full md:w-80 flex justify-between gap-2 text-sm font-bold">
            <span>مبلغ کل فاکتور</span>
            <span><span class="font-technical">{{ preview.total|intcomma_fa }}</span> تومان</span>
        </div>
    </div>
    <p class="fb-inset text-xs">مشتری بالای صفحه‌ی فاکتورش همین پیام را با دکمه‌ی «تایید و پرداخت» می‌بیند.</p>
    <form method="post" data-fb-once class="flex flex-wrap items-center gap-2">
        {% csrf_token %}
        <input type="hidden" name="action" value="issue">
        <input type="hidden" name="deadline_days" value="{{ preview.days }}">
        <input type="hidden" name="seen_total" value="{{ preview.seen_total }}">
        {% if preview.send_sms %}<input type="hidden" name="send_sms" value="on">{% endif %}
        <button type="submit" class="btn btn-primary btn-sm">تایید و صدور</button>
        <a href="{% url 'projects:proforma_editor' project.id %}" class="btn btn-ghost btn-sm">بازگشت و اصلاح</a>
    </form>
</section>
```
**۳. `proforma_editor.html`:** درست قبل از `{% include "projects/partials/proforma_body.html" %}` اضافه کن:
```html
    {% if preview %}{% include "projects/partials/proforma_preview.html" %}{% endif %}
```

### گام ۴ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود (نه `projects/tests_proforma_issue.py`). کل تست‌های موجود را اجرا کن؛ چون `finance/services.py` هسته‌ی مالی است، `TEST_ON_POSTGRES=True python manage.py test finance projects` را هم یک بار اجرا کن و نتیجه را بیاور. اگر تستی که ساخت ردیف فاکتور (`_rebuild_lines`) را می‌سنجید شکست، نام و علتش را گزارش کن؛ رفتار `_rebuild_lines` نباید عوض شده باشد. این‌ها را هم بزن و خروجی را بیاور:
```
python manage.py check
pnpm run build
grep -rn "_rebuild_lines\|build_invoice_lines" --include=*.py .
grep -n "preview\|extend" projects/views.py
```

### گزارش
طبق قواعد ثابت، به‌علاوه خروجی تست روی Postgres و گواهی `pnpm run build`.

### تست دستی (کاربر)
- پیش‌فاکتور تازه: «پیش‌نمایش» ← جدول مثل صفحه‌ی مشتری و پیام مهلت. «بازگشت و اصلاح» ← یک ردیف را عوض کن ← دوباره پیش‌نمایش ← «تایید و صدور».
- با تب دوم، بعد از پیش‌نمایش یک ردیف را عوض کن و در تب اول «تایید و صدور» بزن. پیام «مبلغ تغییر کرده» بیاید و چیزی صادر نشود.
- مهلت نامعتبر (۰ یا ۳۱) در پیش‌نمایش: پیام خطا و هیچ پیش‌نمایشی نیاید.
- بعد از صدور با `client_test` مهلت را در پرتال ببین (بریف ۲).
- با تاریخ‌دادن مهلت به گذشته در `shell` دیتابیس لوکال: بنر «معلق»، ویرایش ردیف، تمدید. (فقط تغییر فیلد `valid_until` یک فاکتور تستی؛ رکورد تازه ساخته نشود.)
- تمدید بدون دلیل رد شود؛ با کاربری که دسترسی قیمت ندارد، صفحه ۴۰۴ بدهد.
- مبلغ فاکتور صادرشده با مبلغ پیش‌نمایش یکی باشد.
- حالت روشن، تاریک و موبایل.

**پرسش غیرمسدودکننده:** اگر پیامک پیش‌فاکتور خاموش بماند و مشتری حساب نداشته باشد، حسابدار فقط از همین پیش‌نمایش می‌فهمد پیامک نرفته. هشدار جدا لازم است؟
**موکول:** بریف ۶ (انتقال ثبت پرداخت، سررسید، لغو و ردیف دستی حسابدار به این صفحه و بیرون‌آوردن‌شان از پرونده‌ی مالی) و بریف ۷ (لینک از نمای پروژه فقط برای مدیر و حسابدار، پاک‌سازی، به‌روزرسانی `docs/`) در پیام بعدی.
