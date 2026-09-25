# فرابخش تهویه — سامانه مدیریت پروژه، انبار و مالی

سامانه‌ی داخلی مدیریت شرکت خدمات تهویه مطبوع: CRM، پروژه و گردش‌کار مراحل اجرا، انبارداری، و فاکتور/پرداخت.

مستند فنی کامل (جدول‌ها، ارتباط‌ها، مثال‌های عددی، توضیح گردش‌کار با سناریو): در آرتیفکت منتشرشده در چت موجود است؛ اگر گم شد، از کلود بخواهید «مستند فنی پروژه فرابخش تهویه» را دوباره لینک بدهد.

## پیش‌نیازها
- Python 3.12+
- PostgreSQL
- Redis (برای کش)
- Node.js + pnpm (برای Tailwind)
- کتابخانه‌های سیستم‌عاملی برای خروجی PDF (در Ubuntu: `sudo apt install libpango-1.0-0 libpangoft2-1.0-0`)

## فعال‌سازی نجوا (Push Notification)
1. مقادیر `NAJVA_API_KEY` و `NAJVA_WEBSITE_ID` را در فایل `.env` تنظیم کنید.
2. آی‌پی سرور خود را در پنل نجوا وایت‌لیست کنید.
3. دستور `python manage.py najva_check` را برای تست اتصال اجرا نمایید.
4. متغیر `NAJVA_ENABLED=True` را در `.env` قرار داده و سرویس را ری‌استارت کنید.

## استقرار روی سرور (Production Deployment)
1. متغیر `DEBUG=False` را در `.env` قرار دهید.
2. دستورات آماده‌سازی استاتیک و مایگریشن:
   ```bash
   pnpm install && pnpm run build
   python manage.py collectstatic --noinput
   python manage.py migrate
   ```
3. تنظیمات Nginx:
   ```nginx
   client_max_body_size 25m;
   proxy_set_header Host $host;
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header X-Forwarded-For $remote_addr;
   ```
4. کرون‌جاب ارسال پیامک‌های جایگزین (هر ۵ دقیقه):
   ```cron
   */5 * * * * /path/to/venv/bin/python /path/to/manage.py process_notification_fallbacks
   ```

## راه‌اندازی اولیه

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # و مقادیر را پر کنید (DB_*, SECRET_KEY, SMS_IR_*, NAJVA_*)

python manage.py migrate
python manage.py createsuperuser
pnpm install
pnpm run build          # ساخت CSS تیلویند
python manage.py runserver
```

## داده‌ی نمونه برای تست
```bash
python manage.py seed_demo_data
```
یک پروژه‌ی کامل با تمام مراحل، فاکتور، پرداخت و چند کاربر با نقش‌های مختلف می‌سازد. یوزرنیم/پسورد کاربران در خروجی ترمینال چاپ می‌شود.

## ساختار اپ‌ها

| اپ | مسئولیت |
|---|---|
| `core` | طرف‌حساب‌ها (`Party`)، رابط‌ها، مکان، تخصص |
| `accounts` | کاربر، نقش، ورود (رمز/OTP) |
| `catalog` | خدمات (درختی)، کالا/متریال، سود متغیر |
| `inventory` | خرید، لات موجودی، حرکت انبار (FIFO + میانگین موزون) |
| `projects` | پروژه، گردش‌کار مراحل، فایل نقشه، تاییدیه |
| `finance` | فاکتور (اسنپ‌شات)، پرداخت چندروشی، دفتر حساب |
| `notifications` | زیرساخت پیامک/پوش (فعلاً بخشی از نقاط اتصال کامنت است) |
| `utils` | ابزار مشترک (عکس، پیامک، پوش) |

ترتیب وابستگی اپ‌ها (برای جلوگیری از import چرخه‌ای):
```
core → accounts → catalog → inventory → projects → finance → notifications → utils
```

## نقش‌های کاربری
- `manager` (مدیر) — دسترسی کامل مدیریتی، می‌تواند هر مرحله را به هرکس ارجاع دهد یا خودش دستی انجام دهد
- `employee` (تکنسین) — فقط به پروژه/مراحلی که مسئول یا کاندیدای آن است دسترسی دارد
- `partner` (شریک تجاری) / `client` (کارفرما) — فقط پرتال محدود (فاکتور + پیشرفت خطی مراحل)

## قوانین طلایی طراحی (حتماً قبل از تغییر کد بخوانید)
1. هیچ قیمتی که در فاکتور چاپ می‌شود از کاتالوگ زنده خوانده نمی‌شود — همیشه در لحظه‌ی صدور کپی (snapshot) می‌شود.
2. `StockMovement` هرگز ویرایش/حذف نمی‌شود؛ اصلاح = رکورد جدید.
3. فاکتور با `document_type=proforma` قابل بازتولید ردیف است؛ با `document_type=final` قفل می‌شود — تغییرات بعدی به‌صورت ردیف جدید (`add_manual_invoice_line`) اضافه می‌شوند، نه ویرایش ردیف قدیمی.
4. پرداخت با روش `credit` (اعتباری) هرگز در `paid_amount` فاکتور حساب نمی‌شود — فقط اجازه می‌دهد کار جلو برود.
5. مسئول هر مرحله با اولویت تعیین می‌شود: مسئول ثابت قالب → استخر کاندیداهای هم‌تخصص (Claim) → کل یک نقش → اگر هیچ‌کدام، در پنل با برچسب «نیازمند تعیین مسئول» دیده می‌شود. مدیر همیشه استثناست و می‌تواند هر مرحله‌ای را به هرکس بدهد یا خودش انجام دهد.
6. رد شدن یک مرحله: اگر `on_reject_go_to` تعریف شده باشد خودکار برمی‌گردد؛ اگر نه، پروژه «معلق» می‌شود تا مدیر تصمیم بگیرد (بازگشت به چرخه یا لغو کامل).
7. مبلغ پرداخت‌های دارای رسید (کارت به کارت، رسید واریز، چک) را همیشه کارشناس از روی رسید می‌نویسد؛ مبلغ واردشده‌ی مشتری فقط «اعلامی» است (`Payment.claimed_amount`). هیچ مسیری نباید چنین پرداختی را بدون مبلغ تاییدشده‌ی کارشناس تایید کند. قوانین ثبت پرداخت فقط در `finance/services.py` (`create_customer_payment`, `approve_payment`) هستند.

## پیامک و پوش
فعلاً **غیرفعال** است — کدش نوشته شده ولی در نقاط اتصال کامنت مانده (دنبال `# TODO(` در `notifications/`, `finance/services.py`, `projects/services.py` بگردید) تا محتوا/تنظیمات نهایی تایید شود.

## تست
```bash
python manage.py test
```
