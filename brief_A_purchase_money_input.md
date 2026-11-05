# بریف A: جداکننده‌ی هزارگان در قیمت خرید

> پیش‌فرض: همه‌ی شاخه‌های قبلی در `main` merge شده‌اند. اگر نشده، به من بگو. این بریف از `main` تازه شاخه می‌گیرد.

## بلوک قواعد ثابت

```text
- شاخه: هر بریف شاخه‌ی خودش، از main تازه. push و merge به main ممنوع.
- git stash و git reset --hard ممنوع.
- پایتون ۳.۱۲ (لوکال، سرور و CI)؛ سینتکس مخصوص ۳.۱۳ به بعد ممنوع.
- هیچ رمز یا کلیدی در فایل، لاگ یا گزارش ننویس.
- تعداد کل تست‌ها کم نشود (مگر حذف/بازنویسی که خود بریف می‌گوید؛ آن را در گزارش با نام بیاور). نام کلاس یا متد تست تکراری ممنوع.
- فقط کار همین گام. کد بریف را عیناً بگذار، «بهتر» نکن. هر جا کد واقعی با بریف نخواند، توقف و گزارش.
- فقط فایل‌هایی که بریف نام برده دست بخورد.
- تصمیم دسترسی فقط با core/capabilities.py. select_for_update همراه select_related فقط با of=("self",).
- در متن UI این کلمه‌ها ممنوع: «اختیاری»، «فعلاً»، «FIFO»، «اسنپ‌شات»، «اتمیک».
- گزارش: تعداد تست قبل و بعد، نام تست‌های جدید/حذف/بازنویسی‌شده، خروجی makemigrations --check --dry-run، نتیجه‌ی هر mutation جدا با نام تست شکست‌خورده (و برگرداندنش)، فهرست فایل‌ها، انحراف‌ها، git log و git branch -a. گزارش جایگزین تست دستی نیست.
- هیچ متنِ آمده از سرور/کاربر با innerHTML، outerHTML، insertAdjacentHTML، document.write یا eval وارد صفحه نشود؛ حتی در کامنت. فقط createElement و textContent.
- در تمپلیت فقط کلاس‌های Tailwind v4 و daisyUI v5. کلاس ممنوع: *-bordered، form-control، label-text، rounded-btn، shadow-sm، badge خالی، btn-warning. بج فقط fb-badge. btn-error فقط با btn-soft.
- در تمپلیت `{{ a.b|default:a.c }}` وقتی a ممکن است None باشد ممنوع؛ از {% if a %} یا |person_name استفاده کن.
- کادر عددی تازه: data-money (مبلغ) یا data-decimal (مقدار اعشاری)؛ type="number" ممنوع.
- روی عنصری که با JS مخفی/ظاهر می‌شود، کلاس‌های display مثل flex/grid ننویس (فقط hidden).
- فایل JS تازه باید در static/src/input.css با @source ثبت شود و pnpm run build بدون خطا اجرا شود.
- آیکون فقط از sprite.svg؛ آیکون ناموجود را نساز.
- ممنوع: ساختن کاربر، تکنسین یا هر رکوردی در دیتابیس واقعی برای آزمایش. بررسی خودکار فقط با تست‌های Django.
- تست موجود را فقط با «بازنویسی» اصلاح کن، نه حذفِ بی‌دلیل. هر جا بریف sed یا حذف می‌گوید، بعدش grep بزن و خروجی را در گزارش بیاور.
- اگر تست قدیمی به‌خاطر همین بریف شکست و نامش در بریف نیست، تصمیم نگیر: نام و علت را گزارش کن و فقط اگر علت مستقیم همین تغییر بود با بازنویسی درستش کن.
```

---

## بریف A: جداکننده‌ی هزارگان در قیمت خرید

**شاخه:** `feat/purchase-money-input`  |  قواعد: بلوک بالا

**توضیح ساده:** در فرم ثبت خرید، کادر «مقدار» و «بهای واحد» از نوع `number` است. هزارگان ندارد و ارقام فارسی را نمی‌پذیرد. مثل پیش‌فاکتور می‌کنیم: کادر مبلغ `data-money` و کادر مقدار `data-decimal`. سرور هم ارقام فارسی و کاما را بپذیرد.

### گام ۰: فقط خواندن
`git status --short`، `git log --oneline -5`، شمارش تست‌ها. خروجی این دو grep را در گزارش بیاور:
`grep -rn 'type="number"' templates/inventory` و `grep -rn "data-cost\|data-qty" templates static/js`.

### گام ۱: تمپلیت
در `templates/inventory/partials/purchase_lines_editor.html`، داخل `<template id="purchase-row-template">`:

قدیم:
```html
            <input type="number" data-qty min="0" step="0.0001" placeholder="مقدار" dir="ltr"
                   class="input input-sm w-24 font-technical">
            <input type="number" data-cost min="0" step="1" placeholder="بهای واحد (تومان)" dir="ltr"
                   class="input input-sm flex-1 min-w-0 font-technical">
```
جدید:
```html
            <input type="text" data-qty data-decimal inputmode="decimal" autocomplete="off" placeholder="مقدار" dir="ltr"
                   aria-label="مقدار" class="input input-sm w-24 font-technical">
            <input type="text" data-cost data-money maxlength="12" inputmode="numeric" autocomplete="off" placeholder="بهای واحد (تومان)" dir="ltr"
                   aria-label="بهای واحد (تومان)" class="input input-sm flex-1 min-w-0 font-technical">
```
در اسکریپت همین فایل، داخل `sync()`:

قدیم:
```js
                var qty = row.querySelector('[data-qty]').value;
                var cost = row.querySelector('[data-cost]').value;
```
جدید:
```js
                var qty = row.querySelector('[data-qty]').value.trim();
                var rawCost = row.querySelector('[data-cost]').value;
                var cost = window.fbMoney ? window.fbMoney.digits(rawCost) : rawCost.replace(/[^0-9]/g, '');
```
بقیه‌ی خطوط `sync` دست نخورد. `money_input.js` در `base.html` از قبل لود می‌شود.

### گام ۲: سرور
در `inventory/services.py`، درست قبل از `def _clean_purchase_lines` این تابع را اضافه کن:
```python
def _purchase_number(raw):
    """عدد ردیف خرید: ارقام فارسی/عربی و جداکننده‌ی هزارگان را می‌پذیرد؛ نامعتبر = InvalidOperation."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace("٫", ".").replace(" ", "")
    if not text or "e" in text.lower():
        raise InvalidOperation
    return Decimal(text)
```
داخل `_clean_purchase_lines`:

قدیم:
```python
            qty = Decimal(str(raw["qty"]))
            unit_cost = Decimal(str(raw["unit_cost"]))
```
جدید:
```python
            qty = _purchase_number(raw["qty"])
            unit_cost = _purchase_number(raw["unit_cost"])
```

### گام ۳: مستندات
در `docs/DESIGN_SYSTEM.md` قانون ۳۰ (شماره بدون تغییر)، جمله‌ی آخر را از این:
`type="number" برای مبلغ ممنوع است (ارقام فارسی را نمی‌پذیرد، با چرخ ماوس مقدار را عوض می‌کند)؛ فقط در ویرایشگر ردیف‌های خرید می‌ماند.`
به این تغییر بده:
`type="number" برای مبلغ ممنوع است (ارقام فارسی را نمی‌پذیرد، با چرخ ماوس مقدار را عوض می‌کند).`

### گام ۴: تست‌ها
فایل تازه `inventory/tests_purchase_money.py`، کلاس `PurchaseMoneyInputTests` (TestCase):
1. فایل تمپلیت را متنی بخوان. تگ `<input` حاوی `data-cost` باید `data-money` و `type="text"` داشته باشد. تگ حاوی `data-qty` باید `data-decimal` داشته باشد. رشته‌ی `type="number"` نباید در فایل باشد.
2. `create_purchase_from_form` با `lines_raw=[{"id": item.id, "qty": "۲٫۵", "unit_cost": "۱,۲۵۰,۰۰۰"}]` ردیفی با qty برابر `2.5` و unit_cost برابر `1250000` بسازد. تأمین‌کننده را با `supplier_party_id` بده و انبار پیش‌فرض بساز.
3. مقدارهای `"abc"`، `"1e3"` و `""` برای qty یا unit_cost ValueError بدهند و هیچ Purchase ساخته نشود.

### mutation (هر کدام جدا، با نام تست شکست‌خورده)
(۱) `type="number"` را به یکی از دو کادر برگردان. (۲) در `_clean_purchase_lines` به `Decimal(str(...))` برگردان.

### تست دستی کاربر (روشن/تاریک و موبایل)
فرم خرید: در بهای واحد `۱۲۳۴۵۶۷` بزن و ببین `1,234,567` می‌شود. حرف تایپ‌شده حذف شود. «جمع ردیف» و «جمع کل» درست حساب شوند. خرید ثبت شود و موجودی درست اضافه شود.
