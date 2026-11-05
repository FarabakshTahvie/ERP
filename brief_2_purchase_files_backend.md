# بریف ۲ — چندفایلی برای خرید: بک‌اند

> ترتیب اجرا: بعد از بریف ۱. شاخه: `feat/purchase-files` (مشترک با بریف ۳). **merge فقط بعد از بریف ۳.** بریف ۲ تنها merge نشود، چون فرم‌های قدیمیِ فایل در آن حالت بی‌اثر می‌مانند.

> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. فقط بازنویسی تست‌های موجودی که با این تغییر می‌شکنند (اگر بریف نام برده) انجام می‌شود.

## بلوک قواعد ثابت

```text
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
- در تمپلیت `{{ a.b|default:a.c }}` وقتی a ممکن است None باشد ممنوع (آرگومان فیلتر خطا می‌دهد)؛ از {% if a %}...{% else %}—{% endif %} استفاده کن.
- کادر عددی تازه: data-money (مبلغ) یا data-decimal (مقدار اعشاری)؛ type="number" ممنوع.
- روی عنصری که با JS مخفی/ظاهر می‌شود، کلاس‌های display مثل flex/grid ننویس (فقط hidden)؛ داخلش یک div با flex بگذار.
- فایل JS تازه باید در static/src/input.css با @source ثبت شود و pnpm run build بدون خطا اجرا شود.
- آیکون فقط از sprite.svg؛ آیکون ناموجود را از خودت نساز.
- ممنوع: ساختن کاربر، تکنسین یا هر رکوردی در دیتابیس واقعی (لوکال یا سرور) برای آزمایش. بررسی خودکار فقط با تست‌های Django.
- seed_test_team فقط اگر کاربر صریحاً خواست. هیچ کاربری پاک نشود.
- تست موجود را فقط با «بازنویسی» اصلاح کن، نه حذفِ بی‌دلیل. هر جا بریف sed یا حذف فایل می‌گوید، بعدش grep بزن و خروجی را در گزارش بیاور.
- اگر یک تست قدیمی به‌خاطر همین بریف شکست و در بریف نامش نیامده، تصمیم نگیر: نامش و علت را گزارش کن و فقط اگر علت مستقیم همین تغییر بود با بازنویسی درستش کن.
```

---

## بریف ۲ — چندفایلی برای خرید: بک‌اند

**توضیح ساده:** به‌جای یک «فایل فاکتور»، هر خرید چند فایل داشته باشد (عکس، PDF، هر نوع دیگر). مدل `PurchaseFile` ساخته می‌شود و فایل‌های قدیمی خودکار به آن منتقل می‌شوند. فیلد `invoice_file` پاک می‌شود. یک endpoint JSON برای آپلود تک‌فایل می‌سازیم (برای نوار پیشرفت). ویوی ثبت خرید برای درخواست XHR جواب JSON می‌دهد. رابط در بریف ۳ می‌آید؛ این بریف تنها merge نشود.

**شاخه:** `feat/purchase-files`
**فایل‌ها:** `inventory/models.py`، `inventory/migrations/*` (سه فایل تازه)، `inventory/services.py`، `inventory/views.py`، `inventory/urls.py`، `finance/accounting.py`، `finance/views_accounting.py`، `utils/navigation.py`، `finance/tests_accounting.py` (فقط یک آرگومان، بازنویسی تست موجود).

### گام ۰ (فقط خواندن)
`git status --short`، `git log --oneline -5`، شمارش تست‌ها. این grepها را بزن و کل خروجی را در گزارش بیاور:
`grep -rn "invoice_file\|_validate_invoice_file\|MAX_INVOICE_FILE_BYTES\|ALLOWED_INVOICE_EXTENSIONS" --include="*.py" --include="*.html" .`
`grep -rn "optimize_named" --include="tests*.py" .`
تست نگهبان بهینه‌ساز تصویر (AST) را پیدا کن؛ در گام ۷ بازنویسی می‌شود. تعداد خرید دارای فایل در دیتابیس لوکال را فقط‌خواندنی بشمار و بنویس:
`python manage.py shell -c "from inventory.models import Purchase; print(Purchase.objects.exclude(invoice_file='').exclude(invoice_file__isnull=True).count())"`

### گام ۱ — مدل (`inventory/models.py`)
بالای فایل `import os` اضافه کن. بعد از کلاس `Purchase` (و قبل از `PurchaseLine`) اضافه کن:
```python
def purchase_file_path(instance, filename):
    return f"purchases/{instance.purchase_id}/files/{filename}"


class PurchaseFile(TimeStampedModel):
    """فایل‌های یک سند خرید (فاکتور، عکس و ...). نام اصلی فایل همان است که کاربر داده؛ نام ذخیره‌شده تصادفی است."""
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="files", verbose_name="سند خرید")
    file = models.FileField(upload_to=purchase_file_path, verbose_name="فایل")
    original_name = models.CharField(max_length=255, blank=True, verbose_name="نام اصلی فایل")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="آپلودکننده")

    class Meta:
        verbose_name = "فایل خرید"
        verbose_name_plural = "فایل‌های خرید"
        ordering = ["created_at", "pk"]

    @property
    def display_name(self):
        return self.original_name or os.path.basename(self.file.name)

    @property
    def is_displayable_image(self):
        return self.file.name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "gif")
```
فعلاً `Purchase.invoice_file` را نگه دار. سپس `python manage.py makemigrations inventory -n purchase_file`.

### گام ۲ — مایگریشن انتقال داده
`python manage.py makemigrations inventory --empty -n copy_invoice_files` و محتوای فایل را این بگذار. خط `dependencies` را همان که ساخته شد نگه دار:
```python
import os
from django.db import migrations


def copy_invoice_files(apps, schema_editor):
    Purchase = apps.get_model("inventory", "Purchase")
    PurchaseFile = apps.get_model("inventory", "PurchaseFile")
    for purchase in Purchase.objects.exclude(invoice_file__isnull=True).exclude(invoice_file=""):
        PurchaseFile.objects.create(
            purchase=purchase, file=purchase.invoice_file.name,
            original_name=os.path.basename(purchase.invoice_file.name)[:255])


class Migration(migrations.Migration):
    dependencies = [("inventory", "<همان که makemigrations گذاشت>")]
    operations = [migrations.RunPython(copy_invoice_files, migrations.RunPython.noop)]
```

### گام ۳ — حذف `invoice_file`
فیلد `invoice_file` را از مدل `Purchase` پاک کن و `python manage.py makemigrations inventory -n remove_purchase_invoice_file` بزن. سه مایگریشن باید جدا باشند؛ نداشتن همه در یک فایل برای Postgres مهم است. بعد `migrate` بزن. تعداد `PurchaseFile` را بشمار (فقط‌خواندنی) و با عدد گام ۰ مقایسه کن.

### گام ۴ — سرویس (`inventory/services.py`)
بالای فایل `import os, re, uuid` اضافه کن و `PurchaseFile` را به ایمپورت مدل‌ها بیفزا.

**حذف:** ثابت‌های `ALLOWED_INVOICE_EXTENSIONS`، `MAX_INVOICE_FILE_BYTES` و تابع `_validate_invoice_file`.

تابع `create_purchase_from_form` را کامل با این جایگزین کن:
```python
@transaction.atomic
def create_purchase_from_form(*, supplier_party_id=None, supplier_party_data=None,
                              purchased_at, invoice_number="", notes="", lines_raw):
    from core.periods import assert_open
    assert_open(purchased_at, "خرید")
    lines = _clean_purchase_lines(lines_raw)
    if not lines:
        raise ValueError("حداقل یک ردیف کالا باید وارد شود.")

    warehouse = Warehouse.objects.filter(is_default=True).first()
    if not warehouse:
        raise ValueError("هیچ انبار پیش‌فرضی تعریف نشده است؛ ابتدا از پنل ادمین یک انبار با «انبار پیش‌فرض» فعال بسازید.")

    supplier = _resolve_supplier_party(party_id=supplier_party_id, party_data=supplier_party_data)
    purchase = Purchase.objects.create(
        supplier=supplier,
        invoice_number=(invoice_number or "").strip(),
        notes=(notes or "").strip(),
        purchased_at=purchased_at,
    )
    items_by_id = {i.pk: i for i in Item.objects.filter(pk__in=[l["item_id"] for l in lines])}
    for line in lines:
        item = items_by_id[line["item_id"]]
        purchase_line = PurchaseLine.objects.create(
            purchase=purchase, item=item, warehouse=warehouse,
            qty=line["qty"], unit_cost=line["unit_cost"],
        )
        receive_stock(
            item=item, warehouse=warehouse, qty=line["qty"], unit_cost=line["unit_cost"],
            received_at=purchased_at, purchase_line=purchase_line,
        )
    return purchase
```
بعد از آن (بالای `CHANGE_KIND_CONSUME`) اضافه کن:
```python
MAX_PURCHASE_FILES = 20
MAX_PURCHASE_FILE_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx


@transaction.atomic
def add_purchase_file(*, purchase_id, uploaded, actor):
    """یک فایل به سند خرید اضافه می‌کند؛ هر نوع فایلی مجاز است. عکس بهینه می‌شود (قانون ۵۷)،
    نام اصلی ثبت و نام ذخیره‌شده تصادفی است. ماه بسته مانع است."""
    from core.periods import assert_open
    from utils.image_utils import optimize_named
    if not can(actor, "purchases.create"):
        raise ValueError("شما اجازه‌ی ارسال فایل برای خرید را ندارید.")
    if uploaded is None:
        raise ValueError("فایلی ارسال نشده است.")
    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "file"
    if uploaded.size > MAX_PURCHASE_FILE_BYTES:
        raise ValueError(f"حجم «{name}» بیشتر از ۲۵ مگابایت است.")
    try:
        purchase = Purchase.objects.select_for_update(of=("self",)).get(pk=purchase_id)
    except (Purchase.DoesNotExist, TypeError, ValueError):
        raise ValueError("این خرید پیدا نشد.")
    assert_open(purchase.purchased_at, "اصلاح خرید")
    if purchase.files.count() >= MAX_PURCHASE_FILES:
        raise ValueError(f"حداکثر {MAX_PURCHASE_FILES} فایل برای هر خرید مجاز است.")
    uploaded, name = optimize_named(uploaded, name)
    ext = re.sub(r"[^a-z0-9]", "", name.rsplit(".", 1)[-1].lower())[:8] if "." in name else ""
    uploaded.name = f"{uuid.uuid4().hex[:16]}.{ext or 'bin'}"
    return PurchaseFile.objects.create(purchase=purchase, file=uploaded, original_name=name, uploaded_by=actor)
```

### گام ۵ — `finance/accounting.py` (`update_purchase`)
فقط این‌ها حذف شوند و بقیه‌ی تابع دست نخورد:
- پارامتر `invoice_file=None` از امضا.
- `_validate_invoice_file` از ایمپورت `from inventory.services import (...)`.
- خط `from utils.image_utils import optimize_named`.
- این بلوک:
```python
    if invoice_file:
        _validate_invoice_file(invoice_file)
        purchase.invoice_file, _name = optimize_named(invoice_file, invoice_file.name or "")
        changes.append("فایل فاکتور")
```

### گام ۶ — ویوها و URL
در `finance/views_accounting.py` در `purchase_edit` فقط خط `invoice_file=request.FILES.get("invoice_file"),` پاک شود.

در `inventory/views.py` ایمپورت را `from core.capabilities import can, cap_required` کن و `purchase_new` را کامل با این جایگزین کن:
```python
@login_required
@user_passes_test(user_can_create_purchases)
def purchase_new(request):
    if request.method == "POST":
        ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        def fail(message):
            if ajax:
                return JsonResponse({"ok": False, "error": message})
            messages.error(request, message)
            return redirect("inventory:purchase_new")

        raw_date = (request.POST.get("purchased_at") or "").strip()
        if raw_date:
            try:
                purchase_date = JalaliDateField().clean(raw_date)
            except ValidationError as e:
                return fail(" ".join(e.messages))
        else:
            purchase_date = timezone.localdate()
        purchased_at = timezone.make_aware(datetime.combine(purchase_date, timezone.localtime().time()))

        lines_raw = _parse_json_lines(request.POST.get("lines_json"))
        supplier_party_id = request.POST.get("supplier_party_id") or None
        supplier_party_data = None if supplier_party_id else _extract_supplier_party_data(request.POST)

        try:
            purchase = create_purchase_from_form(
                supplier_party_id=supplier_party_id,
                supplier_party_data=supplier_party_data,
                purchased_at=purchased_at,
                invoice_number=request.POST.get("invoice_number", ""),
                notes=request.POST.get("notes", ""),
                lines_raw=lines_raw,
            )
        except ValueError as e:
            return fail(str(e))

        messages.success(request, "خرید با موفقیت ثبت شد و موجودی کالاها به‌روزرسانی شد.")
        if ajax:
            detail = (reverse("finance:accounting_purchase", args=[purchase.id])
                      if can(request.user, "accounting.access") else reverse("home"))
            return JsonResponse({"ok": True, "redirect": reverse("home"), "project_url": detail,
                                 "upload_url": reverse("inventory:purchase_file_upload", args=[purchase.id])})
        return redirect("home")

    return render(request, "inventory/purchase_new.html", {
        "items": Item.objects.filter(is_active=True).order_by("name"),
        "today_jalali": jalali_str(timezone.localdate(), fmt="%Y/%m/%d"),
        **item_form_choices(),
    })


@cap_required("purchases.create")
@require_POST
def purchase_file_upload(request, purchase_id):
    """آپلود یک فایل (JSON)؛ هر فایل یک درخواست تا نوار پیشرفت هر فایل جدا باشد."""
    try:
        f = add_purchase_file(purchase_id=purchase_id, uploaded=request.FILES.get("file"), actor=request.user)
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": f.id, "name": f.display_name})
```
`add_purchase_file` را به ایمپورت `from .services import (...)` اضافه کن.

در `inventory/urls.py` بعد از `purchase_new`:
```python
    path("inventory/purchases/<int:purchase_id>/files/", views.purchase_file_upload, name="purchase_file_upload"),
```
در `utils/navigation.py` در `NON_PAGE` اضافه کن: `"inventory:purchase_file_upload"`.

### گام ۷ — بازنویسی تست‌های قدیمی
- در `finance/tests_accounting.py::OverviewNumbersTests.test_overview_numbers` آرگومان `invoice_file=None,` را از فراخوانی `create_purchase_from_form` پاک کن.
- تست نگهبان بهینه‌ساز تصویر (AST) را که در گام ۰ پیدا کردی: هر جا `create_purchase_from_form` را در فهرست نقاط اعمال دارد، با `add_purchase_file` جایگزین کن.
- هر تست دیگری که در grep گام ۰ آمد، فقط با بازنویسی درست شود و نامش در گزارش بیاید.

### گام ۸ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود. کل تست‌های موجود را اجرا کن؛ خروجی `migrate`، شمارش قبل/بعد از انتقال فایل‌ها، فهرست تست‌های بازنویسی‌شده و `python manage.py makemigrations --check --dry-run` را در گزارش بیاور. تست روی Postgres هم اجرا شود: `TEST_ON_POSTGRES=True`.

**تست دستی:** ندارد؛ بعد از بریف ۳ با هم.
**merge نشود** تا بریف ۳ تمام شود.
