# بریف B: نرمال‌سازی شماره‌ها (ثبت پروژه و خرید)

> پیش‌فرض: همه‌ی شاخه‌های قبلی (از جمله بریف A) در `main` merge شده‌اند. اگر نشده، به من بگو. این بریف از `main` تازه شاخه می‌گیرد.

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

## بریف B: نرمال‌سازی شماره‌ها (ثبت پروژه و خرید)

**شاخه:** `fix/phone-normalize`  |  قواعد: بلوک بالا

**توضیح ساده:** «۰۹۱۲…» و «0912…» برای سیستم دو رشته‌ی متفاوت‌اند، برای همین یک شماره دو بار ثبت شد. شماره قبل از جستجو و ذخیره به ارقام لاتین و بدون فاصله تبدیل می‌شود. تبدیل را سه جا می‌گذاریم: توابع سرویس، ویوی جستجوی طرف‌حساب، و `Party.save()` که هیچ مسیری، حتی ادمین، دورش نزند.

### گام ۰: فقط خواندن
`git status --short`، `git log --oneline -5`، شمارش تست. خروجی این grep را بیاور:
`grep -rn "phone_number" projects/views.py inventory/views.py projects/services.py inventory/services.py core/models.py`

### گام ۱: توابع کمکی
در `utils/utils.py` (`re` از قبل import شده)، انتهای فایل:
```python
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_latin_digits(value):
    """ارقام فارسی و عربی ← لاتین. None ← رشته‌ی خالی."""
    return str(value if value is not None else "").translate(_DIGIT_MAP)


def normalize_phone(raw):
    """شماره با ارقام لاتین، بدون فاصله، خط‌تیره، پرانتز و نیم‌فاصله.
    پیش‌شماره‌ی «+98» یا «0098» روی شماره‌ی کامل به «0» تبدیل می‌شود."""
    text = re.sub(r"[\s\-()\u200c\u200e\u200f]", "", to_latin_digits(raw))
    for prefix in ("+98", "0098"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            return "0" + text[len(prefix):]
    return text
```

### گام ۲: مدل
در `core/models.py`، کلاس `Party`، بعد از `__str__` و قبل از `clean` اضافه کن:
```python
    def save(self, *args, **kwargs):
        from utils.utils import normalize_phone, to_latin_digits
        self.phone_number = normalize_phone(self.phone_number)
        self.secondary_phone = normalize_phone(self.secondary_phone)
        self.national_code = to_latin_digits(self.national_code).strip() or None
        super().save(*args, **kwargs)
```
مایگریشن لازم نیست؛ `makemigrations --check` باید تمیز باشد.

### گام ۳: ثبت پروژه
در `projects/services.py` یک تابع ماژول اضافه کن (مثلاً قبل از `create_project_from_technician_intake`):
```python
def _normalized_party_data(data):
    """کپی اطلاعات طرف‌حساب با شماره و کد ملی نرمال‌شده؛ None یا خالی دست‌نخورده برمی‌گردد."""
    if not data:
        return data
    from utils.utils import normalize_phone, to_latin_digits
    out = dict(data)
    out["phone_number"] = normalize_phone(out.get("phone_number"))
    if "national_code" in out:
        out["national_code"] = to_latin_digits(out["national_code"]).strip() or None
    return out
```
داخل `create_project_from_technician_intake`، درست قبل از `if party_id:` (اولین‌بار) این دو خط را اضافه کن و هیچ چیز دیگر را عوض نکن:
```python
    party_data = _normalized_party_data(party_data)
    owner_party_data = _normalized_party_data(owner_party_data)
```

### گام ۴: ثبت خرید
در `inventory/services.py::_resolve_supplier_party`:

قدیم:
```python
    if not party_data or not party_data.get("phone_number"):
        raise ValueError("اطلاعات تأمین‌کننده ناقص است.")
    if Party.objects.filter(phone_number=party_data["phone_number"]).exists():
        raise ValueError("طرف‌حسابی با این شماره از قبل وجود دارد؛ لطفاً همان را انتخاب کنید.")
    party_data = dict(party_data)
    party_data["is_supplier"] = True
```
جدید:
```python
    from utils.utils import normalize_phone, to_latin_digits
    party_data = dict(party_data or {})
    party_data["phone_number"] = normalize_phone(party_data.get("phone_number"))
    if "national_code" in party_data:
        party_data["national_code"] = to_latin_digits(party_data["national_code"]).strip() or None
    if not party_data["phone_number"]:
        raise ValueError("اطلاعات تأمین‌کننده ناقص است.")
    if Party.objects.filter(phone_number=party_data["phone_number"]).exists():
        raise ValueError("طرف‌حسابی با این شماره از قبل وجود دارد؛ لطفاً همان را انتخاب کنید.")
    party_data["is_supplier"] = True
```

### گام ۵: جستجوی طرف‌حساب
در `projects/views.py`: import را به `from utils.utils import separate_digits, normalize_phone` تغییر بده. در `new_project_party_search`:

قدیم: `phone = request.GET.get("phone_number", "").strip()`
جدید: `phone = normalize_phone(request.GET.get("phone_number", ""))`

### گام ۶: تست‌ها
فایل تازه `core/tests_phone_normalize.py`، کلاس `PhoneNormalizeTests` (TestCase):
1. `normalize_phone` روی این جفت‌ها: `"۰۹۱۲۳۴۵۶۷۸۹"`، `"٠٩١٢٣٤٥٦٧٨٩"`، `"+98 912 345 6789"`، `"0098-912-345-6789"` همه ← `"09123456789"`. `None` ← `""`. `"05133873734"` بدون تغییر.
2. `Party.objects.create(name="الف", is_client=True, phone_number="۰۹۱۲۳۴۵۶۷۸۹", national_code="")` ← در دیتابیس شماره لاتین و national_code برابر None.
3. ثبت پروژه: `build_workflow_v3(make_default=True)` و طرف‌حساب داخلی را مثل `tests_intake.py` آماده کن. دو بار `create_project_from_technician_intake(created_by=کاربر پذیرش, party_data={name, brand_name:"", entity_type:"individual", phone_number, national_code:None, is_partner:False, is_client:True}, visit_date=..., issue_proforma=False, project_name="پروژه")` صدا بزن، یک بار با شماره‌ی فارسی و بار دوم با همان شماره‌ی لاتین. بار دوم ValueError («از قبل وجود دارد») بدهد و فقط یک Party با آن شماره باشد. همین‌طور owner_party_data با شماره‌ی فارسی لاتین ذخیره شود.
4. خرید: `create_purchase_from_form(supplier_party_data={name, entity_type:"individual", phone_number:"۰۹۱۲…"}, ...)` یک Party با `is_supplier` و شماره‌ی لاتین بسازد. بار دوم با همان شماره لاتین ValueError بدهد. انبار پیش‌فاکتور و کالا را خودت بساز.
5. ویوی `projects:new_project_party_search` با `?phone_number=۰۹۱۲…` برای کاربر حسابدار (`make_accountant`): طرف‌حسابی که با شماره‌ی لاتین ساخته شده پیدا شود (پاسخ شامل `party_id` و نام او).

### mutation (هر کدام جدا)
(۱) فراخوان `_normalized_party_data` را از intake بردار ← تست ۳. (۲) نرمال‌سازی `_resolve_supplier_party` را بردار ← تست ۴. (۳) نرمال‌سازی ویوی جستجو را بردار ← تست ۵. (۴) `save()` را در Party بردار ← تست ۲.

### تست دستی کاربر
در «ثبت پروژه» یک شماره را با ارقام فارسی تایپ کن: همان طرف‌حساب قبلی پیدا شود. شماره‌ی تازه با کیبورد فارسی ثبت شود، دوباره با ارقام انگلیسی بزن و بگو «از قبل هست». در «ثبت خرید» همین دو را برای تأمین‌کننده امتحان کن. در پروفایل Party شماره لاتین دیده شود.

**نکته‌ها:** روی سرور پروژه‌ای نیست، پس مایگریشن داده نمی‌نویسم. ردیف‌های تکراری لوکال را خودت پاک کن. فرم ورود با OTP و فرم ثبت کاربر هنوز فقط ارقام لاتین را می‌پذیرند. اگر خواستی، بریف جدا می‌شود.
