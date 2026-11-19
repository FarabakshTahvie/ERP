## قواعد ثابت:
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

### بریف: افزودن تب «نیروها» به کارت‌های بانکی (`feat/bank-cards-tabs`)

#### توضیح ساده
در صفحه‌ی کارت‌های بانکی دو تب **«فرابخش»** و **«نیروها»** داریم. همه‌ی کارت‌های ثبت‌شده‌ی قبلی خودکار در تب «فرابخش» می‌مانند. مدیر و حسابدار هنگام ثبت یا ویرایش کارت انتخاب می‌کنند کارت مال کدام تب باشد و با زدن دکمه‌ی «افزودن کارت» در هر تب، همان تب به‌صورت پیش‌فرض انتخاب شده است. در فرم پرداخت مشتری فقط کارت‌های «فرابخش» می‌آیند و تب «نیروها» فقط برای مدیر و حسابدار باز است.

#### فایل‌هایی که دست می‌خورند
- `finance/models.py` (+ مایگریشن تازه در `finance/migrations/`)
- `finance/admin.py`
- `finance/services.py`
- `finance/templatetags/finance_tags.py`
- `finance/views.py`
- `templates/finance/partials/bank_card_fields.html`
- `templates/finance/bank_cards.html`
- `static/js/bank_cards.js`
- `finance/tests_bank_cards.py`

> قواعد ثابت نشست اول کار رعایت شوند: شاخه‌ی تازه `feat/bank-cards-tabs` از `main` تازه، بدون `push`/`merge` به `main`، بدون `git stash`/`reset --hard`، پایتون ۳٫۱۲ (`.venv`)، هر جا کد واقعی با بریف نخواند توقف و گزارش.

---

#### گام ۰ — فقط‌خواندنی (بررسی وضعیت و آماده‌سازی شاخه)
۱. وضعیت گیت و آخرین کامیت‌ها را بررسی کن:
   - `git status --short`
   - `git log --oneline -5`
   - اگر شاخه‌ی کاری تمیز و روی `main` تازه است، شاخه‌ی `feat/bank-cards-tabs` را بساز.
۲. همه‌ی جاهایی که `BankCard` یا `bank_cards_slider` یا `bank_card` استفاده شده با `grep` بسنج و مطمئن شو فقط فایل‌های فهرست بالا هستند.
۳. آخرین مایگریشن پوشه‌ی `finance/migrations/` را ببین و کل تست‌های فعلی پروژه را با پایتونِ `.venv` اجرا کن تا عدد قبل از تغییر مشخص شود.

---

#### گام ۱ — مدل `BankCard`، مایگریشن و پنل ادمین

**۱. در `finance/models.py`:**

قدیم:
```python
class BankCard(TimeStampedModel):
    """کارت بانکی خودِ شرکت؛ برای نمایش به مشتری در پرداخت کارت به کارت و صفحهی عمومی."""
    bank = models.CharField(max_length=20, choices=BANK_CHOICES, default="other", verbose_name="بانک")
    other_bank_name = models.CharField(max_length=60, blank=True, verbose_name="نام بانک (وقتی «سایر» است)")
```

جدید:
```python
class BankCard(TimeStampedModel):
    """کارت بانکی (فرابخش برای دریافت از مشتری، و نیروها برای پرداخت به همکاران؛ تب نیروها فقط با bank_cards.manage)."""

    class Category(models.TextChoices):
        FARABAKHSH = "farabakhsh", "فرابخش"
        STAFF = "staff", "نیروها"

    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.FARABAKHSH,
        db_index=True, verbose_name="بخش",
    )
    bank = models.CharField(max_length=20, choices=BANK_CHOICES, default="other", verbose_name="بانک")
    other_bank_name = models.CharField(max_length=60, blank=True, verbose_name="نام بانک (وقتی «سایر» است)")
```

**۲. مایگریشن بساز و اعمال کن:**
- دستور `makemigrations finance` را با پایتون `.venv` اجرا کن (به‌خاطر `default=Category.FARABAKHSH` همه‌ی کارت‌های موجود خودکار در `farabakhsh` قرار می‌گیرند).
- سپس `migrate` و `makemigrations --check --dry-run` را اجرا کن.

**۳. در `finance/admin.py`:**

قدیم:
```python
@admin.register(BankCard)
class BankCardAdmin(ModelAdmin):
    list_display = ("bank_display", "holder_name", "card_number", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("is_active", "bank")
    search_fields = ("holder_name", "card_number", "other_bank_name")
    ordering = ("order", "id")
    fields = ("bank", "other_bank_name", "holder_name", "card_number", "sheba", "cvv2", "expiry", "is_active", "order")
```

جدید:
```python
@admin.register(BankCard)
class BankCardAdmin(ModelAdmin):
    list_display = ("bank_display", "category", "holder_name", "card_number", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("category", "is_active", "bank")
    search_fields = ("holder_name", "card_number", "other_bank_name")
    ordering = ("order", "id")
    fields = ("category", "bank", "other_bank_name", "holder_name", "card_number", "sheba", "cvv2", "expiry", "is_active", "order")
```

---

#### گام ۲ — سرویس، تگ تمپلیت و ویو

**۱. در `finance/services.py`:**

قدیم:
```python
@transaction.atomic
def create_bank_card(*, actor, bank, holder_name, card_number, other_bank_name="", sheba="", cvv2="", expiry=""):
    """ثبت کارت بانکی شرکت (فقط مدیر یا حسابدار). هر ایرادی ValueError فارسی؛ کارت همان لحظه فعال و آخر فهرست می‌نشیند."""
    from django.core.exceptions import ValidationError
    from core.capabilities import can
    if not can(actor, "bank_cards.manage"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند کارت بانکی ثبت کند.")
    last = BankCard.objects.aggregate(m=models.Max("order"))["m"]
    card = BankCard(
        bank=(bank or "").strip(), other_bank_name=(other_bank_name or "").strip(),
        holder_name=holder_name or "", card_number=card_number or "", sheba=sheba or "",
        cvv2=cvv2 or "", expiry=expiry or "", is_active=True,
        order=0 if last is None else last + 1,
    )
    try:
        card.full_clean()
    except ValidationError as e:
        parts = [m for msgs in e.message_dict.values() for m in msgs]
        raise ValueError(" ".join(parts) or "کارت معتبر نیست.")
    card.save()
    return card


def _require_bank_card_manager(actor):
    from core.capabilities import can
    if not can(actor, "bank_cards.manage"):
        raise ValueError("فقط مدیر یا حسابدار به کارت‌های بانکی دسترسی دارد.")


def _locked_bank_card(card_id):
    try:
        return BankCard.objects.select_for_update(of=("self",)).get(pk=int(card_id))
    except (TypeError, ValueError, BankCard.DoesNotExist):
        raise ValueError("کارت پیدا نشد.")


@transaction.atomic
def update_bank_card(*, actor, card_id, bank, holder_name, card_number, other_bank_name="",
                     sheba="", cvv2="", expiry=""):
    """ویرایش کارت. فیلد خالی یعنی پاک‌شدن (فرم همیشه همه‌ی فیلدها را می‌فرستد). ترتیب و وضعیت فعال دست نمی‌خورد."""
    from django.core.exceptions import ValidationError
    _require_bank_card_manager(actor)
    card = _locked_bank_card(card_id)
    card.bank = (bank or "").strip()
    card.other_bank_name = (other_bank_name or "").strip()
    card.holder_name = holder_name or ""
    card.card_number = card_number or ""
    card.sheba = sheba or ""
    card.cvv2 = cvv2 or ""
    card.expiry = expiry or ""
    try:
        card.full_clean()
    except ValidationError as e:
        parts = [m for msgs in e.message_dict.values() for m in msgs]
        raise ValueError(" ".join(parts) or "کارت معتبر نیست.")
    card.save()
    return card
```

جدید:
```python
def _clean_card_category(raw):
    value = (raw or "").strip()
    if value not in BankCard.Category.values:
        raise ValueError("تب انتخاب‌شده معتبر نیست.")
    return value


@transaction.atomic
def create_bank_card(*, actor, bank, holder_name, card_number, other_bank_name="", sheba="", cvv2="", expiry="",
                     category=BankCard.Category.FARABAKHSH):
    """ثبت کارت بانکی (فقط مدیر یا حسابدار). هر ایرادی ValueError فارسی؛ کارت همان لحظه فعال و آخر فهرست می‌نشیند."""
    from django.core.exceptions import ValidationError
    from core.capabilities import can
    if not can(actor, "bank_cards.manage"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند کارت بانکی ثبت کند.")
    cat = _clean_card_category(category)
    last = BankCard.objects.aggregate(m=models.Max("order"))["m"]
    card = BankCard(
        category=cat, bank=(bank or "").strip(), other_bank_name=(other_bank_name or "").strip(),
        holder_name=holder_name or "", card_number=card_number or "", sheba=sheba or "",
        cvv2=cvv2 or "", expiry=expiry or "", is_active=True,
        order=0 if last is None else last + 1,
    )
    try:
        card.full_clean()
    except ValidationError as e:
        parts = [m for msgs in e.message_dict.values() for m in msgs]
        raise ValueError(" ".join(parts) or "کارت معتبر نیست.")
    card.save()
    return card


def _require_bank_card_manager(actor):
    from core.capabilities import can
    if not can(actor, "bank_cards.manage"):
        raise ValueError("فقط مدیر یا حسابدار به کارت‌های بانکی دسترسی دارد.")


def _locked_bank_card(card_id):
    try:
        return BankCard.objects.select_for_update(of=("self",)).get(pk=int(card_id))
    except (TypeError, ValueError, BankCard.DoesNotExist):
        raise ValueError("کارت پیدا نشد.")


@transaction.atomic
def update_bank_card(*, actor, card_id, bank, holder_name, card_number, other_bank_name="",
                     sheba="", cvv2="", expiry="", category=None):
    """ویرایش کارت. فیلد خالی یعنی پاک‌شدن (فرم همیشه همه‌ی فیلدها را می‌فرستد). category=None یعنی تغییر نکند."""
    from django.core.exceptions import ValidationError
    _require_bank_card_manager(actor)
    card = _locked_bank_card(card_id)
    if category is not None:
        card.category = _clean_card_category(category)
    card.bank = (bank or "").strip()
    card.other_bank_name = (other_bank_name or "").strip()
    card.holder_name = holder_name or ""
    card.card_number = card_number or ""
    card.sheba = sheba or ""
    card.cvv2 = cvv2 or ""
    card.expiry = expiry or ""
    try:
        card.full_clean()
    except ValidationError as e:
        parts = [m for msgs in e.message_dict.values() for m in msgs]
        raise ValueError(" ".join(parts) or "کارت معتبر نیست.")
    card.save()
    return card
```

**۲. در `finance/templatetags/finance_tags.py`:**

قدیم:
```python
@register.inclusion_tag("finance/partials/bank_cards_slider.html", takes_context=True)
def bank_cards_slider(context):
    """CVV2 و تاریخ انقضا فقط برای دارندگان bank_cards.manage؛ مشتری فقط شماره و شبا را می‌بیند."""
    user = getattr(context.get("request"), "user", None)
    show_secrets = bool(user is not None and user.is_authenticated and can(user, "bank_cards.manage"))
    cards = list(BankCard.objects.filter(is_active=True))
    for c in cards:
        c.logo = logo_url(c.bank)
    return {"cards": cards, "show_secrets": show_secrets}
```

جدید:
```python
@register.inclusion_tag("finance/partials/bank_cards_slider.html", takes_context=True)
def bank_cards_slider(context, category=BankCard.Category.FARABAKHSH):
    """CVV2 و تاریخ انقضا فقط برای دارندگان bank_cards.manage؛ مشتری فقط شماره و شبا را می‌بیند.
    بدون دسترسی bank_cards.manage همیشه فقط کارت‌های «فرابخش» برمی‌گردد."""
    user = getattr(context.get("request"), "user", None)
    manage = bool(user is not None and user.is_authenticated and can(user, "bank_cards.manage"))
    target = category if (manage and category in BankCard.Category.values) else BankCard.Category.FARABAKHSH
    cards = list(BankCard.objects.filter(is_active=True, category=target))
    for c in cards:
        c.logo = logo_url(c.bank)
    return {"cards": cards, "show_secrets": manage}
```

**۳. در `finance/views.py`:**

قدیم:
```python
@login_required
def bank_cards_page(request):
    """هر کاربر واردشده شماره و شبا را می‌بیند. CVV2، انقضا و مدیریت کارت‌ها فقط با bank_cards.manage."""
    manage = can(request.user, "bank_cards.manage")
    return render(request, "finance/bank_cards.html", {
        "bank_choices": BANK_CHOICES, "can_manage": manage,
        "all_cards": list(BankCard.objects.all()) if manage else [],
    })


@cap_required("bank_cards.manage")
@require_POST
def bank_card_create(request):
    try:
        create_bank_card(
            actor=request.user, bank=request.POST.get("bank", ""),
            other_bank_name=request.POST.get("other_bank_name", ""),
            holder_name=request.POST.get("holder_name", ""), card_number=request.POST.get("card_number", ""),
            sheba=request.POST.get("sheba", ""), cvv2=request.POST.get("cvv2", ""),
            expiry=request.POST.get("expiry", ""))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})


@cap_required("bank_cards.manage")
@require_POST
def bank_card_update(request, card_id):
    try:
        update_bank_card(
            actor=request.user, card_id=card_id, bank=request.POST.get("bank", ""),
            other_bank_name=request.POST.get("other_bank_name", ""),
            holder_name=request.POST.get("holder_name", ""), card_number=request.POST.get("card_number", ""),
            sheba=request.POST.get("sheba", ""), cvv2=request.POST.get("cvv2", ""),
            expiry=request.POST.get("expiry", ""))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})
```

جدید:
```python
@login_required
def bank_cards_page(request):
    """هر کاربر واردشده کارت‌های «فرابخش» را می‌بیند. تب «نیروها»، CVV2، انقضا و مدیریت فقط با bank_cards.manage."""
    manage = can(request.user, "bank_cards.manage")
    requested = (request.GET.get("tab") or "").strip()
    active_tab = requested if (manage and requested in BankCard.Category.values) else BankCard.Category.FARABAKHSH
    return render(request, "finance/bank_cards.html", {
        "bank_choices": BANK_CHOICES,
        "category_choices": BankCard.Category.choices,
        "can_manage": manage,
        "active_tab": active_tab,
        "all_cards": list(BankCard.objects.filter(category=active_tab)) if manage else [],
    })


@cap_required("bank_cards.manage")
@require_POST
def bank_card_create(request):
    try:
        card = create_bank_card(
            actor=request.user,
            category=request.POST.get("category", BankCard.Category.FARABAKHSH),
            bank=request.POST.get("bank", ""),
            other_bank_name=request.POST.get("other_bank_name", ""),
            holder_name=request.POST.get("holder_name", ""), card_number=request.POST.get("card_number", ""),
            sheba=request.POST.get("sheba", ""), cvv2=request.POST.get("cvv2", ""),
            expiry=request.POST.get("expiry", ""))
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "category": card.category})


@cap_required("bank_cards.manage")
@require_POST
def bank_card_update(request, card_id):
    try:
        kw = {"category": request.POST.get("category")} if "category" in request.POST else {}
        card = update_bank_card(
            actor=request.user, card_id=card_id, bank=request.POST.get("bank", ""),
            other_bank_name=request.POST.get("other_bank_name", ""),
            holder_name=request.POST.get("holder_name", ""), card_number=request.POST.get("card_number", ""),
            sheba=request.POST.get("sheba", ""), cvv2=request.POST.get("cvv2", ""),
            expiry=request.POST.get("expiry", ""), **kw)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "category": card.category})
```

---

#### گام ۳ — تمپلیت‌ها و جاوااسکریپت (+ بیلد CSS)

**۱. در `templates/finance/partials/bank_card_fields.html`:**

قدیم:
```html
<div class="fb-field">
    <label class="fb-label" for="{{ prefix }}-bank">بانک</label>
```

جدید:
```html
<div class="fb-field">
    <label class="fb-label" for="{{ prefix }}-category">تب</label>
    <select id="{{ prefix }}-category" name="category" required class="select w-full">
        {% for value, label in category_choices %}<option value="{{ value }}" {% if active_tab == value %}selected{% endif %}>{{ label }}</option>{% endfor %}
    </select>
</div>
<div class="fb-field">
    <label class="fb-label" for="{{ prefix }}-bank">بانک</label>
```

**۲. در `templates/finance/bank_cards.html`:**

قدیم:
```html
        {% if can_manage %}
        <button type="button" class="btn btn-primary btn-sm" onclick="document.getElementById('bankcard-dialog').showModal()">
            {% icon "plus" "w-4 h-4" %} افزودن کارت
        </button>
        {% endif %}
    </div>

    {% bank_cards_slider %}
```

جدید:
```html
        {% if can_manage %}
        <button type="button" class="btn btn-primary btn-sm" data-bankcard-add>
            {% icon "plus" "w-4 h-4" %} افزودن کارت
        </button>
        {% endif %}
    </div>

    {% if can_manage %}
    <div role="tablist" class="tabs tabs-border">
        {% for value, label in category_choices %}
        <a href="?tab={{ value }}" role="tab" class="tab {% if active_tab == value %}tab-active{% endif %}">{{ label }}</a>
        {% endfor %}
    </div>
    {% endif %}

    {% bank_cards_slider active_tab %}
```

و در همین فایل `templates/finance/bank_cards.html` روی دکمه‌ی ویرایش:

قدیم:
```html
                <button type="button" class="btn btn-ghost btn-xs" data-bankcard-edit
                        data-url="{% url 'finance:bank_card_update' c.id %}" data-bank="{{ c.bank }}" data-other="{{ c.other_bank_name }}"
```

جدید:
```html
                <button type="button" class="btn btn-ghost btn-xs" data-bankcard-edit
                        data-url="{% url 'finance:bank_card_update' c.id %}" data-category="{{ c.category }}" data-bank="{{ c.bank }}" data-other="{{ c.other_bank_name }}"
```

**۳. در `static/js/bank_cards.js`:**

(الف) در `initCardForms`:

قدیم:
```javascript
        window.fbSend(url, new FormData(form), window.FB_CSRF).then(function (res) {
          if (res.ok) { window.location.reload(); return; }
          btn.disabled = false;
          err.textContent = res.error || 'ثبت نشد.';
          err.classList.remove('hidden');
        });
```

جدید:
```javascript
        window.fbSend(url, new FormData(form), window.FB_CSRF).then(function (res) {
          if (res.ok) {
            if (res.category) {
              var nextUrl = new URL(window.location.href);
              nextUrl.searchParams.set('tab', res.category);
              window.location.assign(nextUrl.toString());
            } else {
              window.location.reload();
            }
            return;
          }
          btn.disabled = false;
          err.textContent = res.error || 'ثبت نشد.';
          err.classList.remove('hidden');
        });
```

(ب) در شنونده‌ی کلیک دکمه‌های مدیریت:

قدیم:
```javascript
    var edit = e.target.closest('[data-bankcard-edit]');
    if (edit) {
      var editDialog = document.getElementById('bankcard-edit-dialog');
      var editForm = editDialog && editDialog.querySelector('[data-bankcard-form]');
      if (!editForm) return;
      var d = edit.dataset;
      editForm.setAttribute('action', d.url);
      editForm.querySelector('[name="bank"]').value = d.bank;
```

جدید:
```javascript
    var add = e.target.closest('[data-bankcard-add]');
    if (add) {
      var addDialog = document.getElementById('bankcard-dialog');
      var addForm = addDialog && addDialog.querySelector('[data-bankcard-form]');
      if (!addDialog || !addForm) return;
      addForm.reset();
      addForm._syncOther();
      addForm.querySelector('[data-bankcard-error]').classList.add('hidden');
      addForm.querySelector('button[type="submit"]').disabled = false;
      addDialog.showModal();
      return;
    }

    var edit = e.target.closest('[data-bankcard-edit]');
    if (edit) {
      var editDialog = document.getElementById('bankcard-edit-dialog');
      var editForm = editDialog && editDialog.querySelector('[data-bankcard-form]');
      if (!editForm) return;
      var d = edit.dataset;
      editForm.setAttribute('action', d.url);
      var catField = editForm.querySelector('[name="category"]');
      if (catField) catField.value = d.category || 'farabakhsh';
      editForm.querySelector('[name="bank"]').value = d.bank;
```

**۴. بیلد CSS:**
- `pnpm run build` را اجرا کن تا خروجی Tailwind/daisyUI به‌روز باشد.

---

#### گام ۴ — تست‌ها

در انتهای `finance/tests_bank_cards.py` این کدها را اضافه کن:

قدیم (خط آخر `finance/tests_bank_cards.py`):
```python
    def test_bank_cards_js_is_registered_for_tailwind(self):
        css = (self.BASE / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn('@source "../js/bank_cards.js";', css)
```

جدید:
```python
    def test_bank_cards_js_is_registered_for_tailwind(self):
        css = (self.BASE / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn('@source "../js/bank_cards.js";', css)


class BankCardCategoryTests(TestCase):
    def setUp(self):
        self.accountant = make_accountant("bcc_acc")
        self.tech = User.objects.create_user(username="bcc_tech", password="pw", role=User.Role.EMPLOYEE)

    def test_default_category_is_farabakhsh_and_invalid_rejected(self):
        c1 = make_card()
        self.assertEqual(c1.category, BankCard.Category.FARABAKHSH)

        from finance.services import create_bank_card, update_bank_card
        c2 = create_bank_card(actor=self.accountant, bank="mellat", holder_name="کارت نیرو",
                              card_number=CARD2, category=BankCard.Category.STAFF)
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        for bad in ("", "unknown", "other"):
            with self.assertRaises(ValueError):
                create_bank_card(actor=self.accountant, bank="saman", holder_name="نامعتبر",
                                 card_number=CARD3, category=bad)
        self.assertFalse(BankCard.objects.filter(card_number=CARD3).exists())

        with self.assertRaises(ValueError):
            update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                             holder_name="کارت نیرو", card_number=CARD2, category="bad")
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                         holder_name="کارت نیرو ویرایش", card_number=CARD2)
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.STAFF)

        update_bank_card(actor=self.accountant, card_id=c2.id, bank="mellat",
                         holder_name="کارت نیرو ویرایش", card_number=CARD2,
                         category=BankCard.Category.FARABAKHSH)
        c2.refresh_from_db()
        self.assertEqual(c2.category, BankCard.Category.FARABAKHSH)


class BankCardViewCategoryTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="bcv_mgr", password="pw", role=User.Role.ADMIN)
        self.accountant = make_accountant("bcv_acc")
        self.tech = User.objects.create_user(username="bcv_tech", password="pw", role=User.Role.EMPLOYEE)
        self.party = Party.objects.create(name="مشتری کارت", is_client=True, phone_number="09128889900")
        self.customer = User.objects.create_user(username="bcv_cli", password="pw", role=User.Role.CLIENT, party=self.party)
        self.company_card = make_card(holder_name="کارت شرکت فرابخش", card_number=CARD1,
                                      cvv2="123", expiry="06/05", category=BankCard.Category.FARABAKHSH)
        self.staff_card = make_card(bank="mellat", holder_name="کارت نیروی فنی", card_number=CARD2,
                                    sheba="", cvv2="999", expiry="07/08", category=BankCard.Category.STAFF)

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_staff_cards_never_appear_in_customer_payment_forms(self):
        from projects.models import ProjectStage, StageApproval, WorkflowStepTemplate, WorkflowTemplate
        tpl = WorkflowTemplate.objects.create(name="قالب کارت پرداخت")
        step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="تایید پیش‌فاکتور",
                                                 requires_payment_selection=True)
        project = Project.objects.create(name="پروژه کارت", partner=self.party, owner=self.party,
                                         workflow_template=tpl, status=Project.Status.IN_PROGRESS)
        invoice = Invoice.objects.create(project=project, number="INV-BC-1", billed_party=self.party,
                                         total_amount=Decimal("500000"), issue_date=timezone.localdate(),
                                         status=Invoice.Status.SENT)
        stage = ProjectStage.objects.create(project=project, step_template=step, order=1,
                                            title="تایید پیش‌فاکتور", status=ProjectStage.Status.WAITING_APPROVAL)
        approval = StageApproval.objects.create(stage=stage, sent_to_party=self.party)

        c = self.login(self.customer)
        for url in (reverse("finance:portal_add_payment", args=[invoice.uuid]),
                    reverse("projects:portal_stage_approval", args=[approval.id])):
            resp = c.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertContains(resp, "کارت شرکت فرابخش")
            self.assertNotContains(resp, "کارت نیروی فنی")
            self.assertNotContains(resp, CARD2)

    def test_tabs_isolation_and_permissions_on_bank_cards_page(self):
        url = reverse("finance:bank_cards")
        for user in (self.manager, self.accountant):
            c = self.login(user)
            r_company = c.get(url)
            self.assertEqual(r_company.status_code, 200)
            self.assertContains(r_company, "کارت شرکت فرابخش")
            self.assertNotContains(r_company, "کارت نیروی فنی")
            self.assertContains(r_company, "?tab=staff")

            r_staff = c.get(url + "?tab=staff")
            self.assertEqual(r_staff.status_code, 200)
            self.assertContains(r_staff, "کارت نیروی فنی")
            self.assertContains(r_staff, "999")
            self.assertNotContains(r_staff, "کارت شرکت فرابخش")

        for user in (self.tech, self.customer):
            c = self.login(user)
            r = c.get(url + "?tab=staff")
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "کارت شرکت فرابخش")
            self.assertNotContains(r, "کارت نیروی فنی")
            self.assertNotContains(r, "?tab=staff")
            self.assertNotContains(r, "123")

    def test_create_and_move_category_via_views(self):
        c = self.login(self.accountant)
        r_bad = c.post(reverse("finance:bank_card_create"), {
            "category": "wrong", "bank": "saman", "holder_name": "تست", "card_number": CARD3,
        })
        self.assertEqual(r_bad.status_code, 400)

        r_ok = c.post(reverse("finance:bank_card_create"), {
            "category": "staff", "bank": "saman", "holder_name": "نیروی جدید", "card_number": CARD3,
        })
        self.assertEqual(r_ok.status_code, 200)
        self.assertEqual(r_ok.json(), {"ok": True, "category": "staff"})
        created = BankCard.objects.get(card_number=CARD3)
        self.assertEqual(created.category, BankCard.Category.STAFF)

        r_move = c.post(reverse("finance:bank_card_update", args=[created.id]), {
            "category": "farabakhsh", "bank": "saman", "holder_name": "نیروی جدید", "card_number": CARD3,
        })
        self.assertEqual(r_move.status_code, 200)
        self.assertEqual(r_move.json(), {"ok": True, "category": "farabakhsh"})
        created.refresh_from_db()
        self.assertEqual(created.category, BankCard.Category.FARABAKHSH)

        for outsider in (self.tech, self.customer):
            oc = self.login(outsider)
            self.assertEqual(oc.post(reverse("finance:bank_card_create"), {
                "category": "staff", "bank": "saman", "holder_name": "x", "card_number": "6037991234567885",
            }).status_code, 404)

    def test_admin_includes_category(self):
        from finance.admin import BankCardAdmin
        self.assertIn("category", BankCardAdmin.list_display)
        self.assertIn("category", BankCardAdmin.list_filter)
        self.assertIn("category", BankCardAdmin.fields)
```

---

#### گام ۵ — اجرای کامل تست‌ها و بررسی mutationها

۱. اجرای کل تست‌ها روی sqlite و سپس با `TEST_ON_POSTGRES=True`:
   - بررسی کن که همه‌ی تست‌های محافظ (از جمله `test_bank_cards_js_has_no_unsafe_html_sinks`، `test_no_duplicate_test_class_or_method_names`، `test_removed_css_classes_in_templates`، `test_forbidden_ui_words_in_templates`) سبز شوند.
۲. **سه mutation را یکی‌یکی امتحان کن، بعد از هر کدام بلافاصله برگردان، و نتیجه‌ی هر کدام را جدا گزارش کن:**
   - **M1 (نمایش در فرم پرداخت مشتری):** در `finance/templatetags/finance_tags.py` فیلتر `category=target` را از `BankCard.objects.filter(is_active=True, category=target)` بردار ← باید `test_staff_cards_never_appear_in_customer_payment_forms` (و `test_tabs_isolation_and_permissions_on_bank_cards_page`) شکست بخورد.
   - **M2 (دسترسی تب نیروها):** در `finance/views.py` شرط `manage` را از `active_tab` بردار و در `finance_tags.py` خط `target = category` بدون چک `manage` بگذار ← باید `test_tabs_isolation_and_permissions_on_bank_cards_page` شکست بخورد.
   - **M3 (اعتبارسنجی `category` در سرویس):** در `finance/services.py` در `create_bank_card` مقدار `category` نامعتبر را بدون خطا بپذیر ← باید `test_default_category_is_farabakhsh_and_invalid_rejected` و `test_create_and_move_category_via_views` شکست بخورند.
۳. کامیت روی شاخه‌ی `feat/bank-cards-tabs` (بدون `push` و بدون `merge` به `main`).

---

#### گزارش خواسته‌شده از دستیار
- تعداد تست قبل و بعد + نام تست‌های جدید/تغییریافته
- خروجی `makemigrations --check --dry-run`
- نتیجه‌ی هر ۳ mutation به‌صورت جداگانه با نام تست شکست‌خورده (و تایید برگرداندنشان)
- فهرست فایل‌های تغییریافته (همراه با نام فایل مایگریشن جدید)
- انحراف‌ها (اگر هست)
- خروجی `git status --short`، `git log --oneline -5` و `git branch -a`
- گواهی اجرای موفق `pnpm run build`
- یادآوری: «گزارش جایگزین تست دستی نیست»

---

#### تست دستی کاربر (بعد از تایید و دیپلوی)
- روی **حالت روشن/تاریک** و **موبایل** صفحه‌ی کارت‌های بانکی را باز کن:
  1. با حساب مدیر/حسابدار وارد «کارت‌های بانکی» شو: همه‌ی کارت‌های قبلی باید در تب **«فرابخش»** باشند.
  2. به تب **«نیروها»** برو و «افزودن کارت» را بزن: تب باید خودکار روی «نیروها» باشد؛ یک کارت ثبت کن و مطمئن شو بعد از ثبت، روی تب «نیروها» می‌ماند و کارت دیده می‌شود.
  3. یک کارت را ویرایش کن و تبش را از «نیروها» به «فرابخش» (و برعکس) جابه‌جا کن و ببین به تب مقصد می‌رود.
  4. روی ردیف کارت‌ها بزن، دکمه‌ی کپی شماره کارت/شبا، فعال/غیرفعال و حذف را امتحان کن.
  5. با حساب **مشتری** (در یک پروژه‌ی منتظر تایید یا پرداخت) گزینه‌ی «کارت به کارت» را انتخاب کن: مطمئن شو فقط کارت‌های «فرابخش» نمایش داده می‌شوند و کارت‌های «نیروها» نیستند.
  6. بعد از هر ثبت یا تغییر، تم و منوی هدر را تست کن تا مشکلی نباشد.
