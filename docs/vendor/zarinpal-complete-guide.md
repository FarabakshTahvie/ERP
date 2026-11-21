# مستند کامل استفاده از درگاه پرداخت زرین‌پال

> این مستند بر اساس صفحات مستندات رسمی زرین‌پال تهیه شده و شامل تمام بخش‌های آن است: درگاه پرداخت، راهنمای اتصال، سرویس تست، لیست خطاها، اعتبارسنجی، چک‌اوت، واحد پولی، پرداخت با کارت مشخص، ریورس، همکاری در فروش، متدهای کمکی، احراز هویت، API با GraphQL، تراکنش‌ها، حساب بانکی، درگاه‌ها، نمونه کد Python و سرویس MCP.
>
> **یادداشت:** صفحات «واحد پولی» (`currency`) و «تنظیمات ارتباط با ترمینال» (`reconciles`) در زمان دریافت محتوا قابل خواندن نبودند. مطالب مربوط به واحد پولی از بخش‌های دیگر همین مستندات (راهنمای اتصال، چک‌اوت و همکاری در فروش) گردآوری شده است.

---

## فهرست مطالب

1. [معرفی درگاه پرداخت](#۱-معرفی-درگاه-پرداخت)
2. [واژگان](#۲-واژگان)
3. [اطلاعات فنی سیستم](#۳-اطلاعات-فنی-سیستم)
4. [نیازمندی‌های امنیتی](#۴-نیازمندی‌های-امنیتی)
5. [راهنمای اتصال به درگاه (مراحل پرداخت)](#۵-راهنمای-اتصال-به-درگاه)
6. [سرویس تست (Sandbox)](#۶-سرویس-تست-sandbox)
7. [لیست خطاها و کدهای وضعیت](#۷-لیست-خطاها-و-کدهای-وضعیت)
8. [اعتبارسنجی تراکنش (خودکار/غیرخودکار)](#۸-اعتبارسنجی-تراکنش-خودکارغیرخودکار)
9. [میان‌پی (صفحه چک‌اوت)](#۹-میانپی-صفحه-چکاوت)
10. [واحد پولی](#۱۰-واحد-پولی)
11. [پرداخت با کارت مشخص و ذخیره کارت](#۱۱-پرداخت-با-کارت-مشخص-و-ذخیره-کارت)
12. [ریورس تراکنش](#۱۲-ریورس-تراکنش)
13. [همکاری در فروش (referrer_id)](#۱۳-همکاری-در-فروش-referrer_id)
14. [متد unVerified (پرداخت‌های تأیید نشده)](#۱۴-متد-unverified)
15. [استعلام وضعیت پرداخت](#۱۵-استعلام-وضعیت-پرداخت)
16. [محاسبه کارمزد (FeeCalculation)](#۱۶-محاسبه-کارمزد-feecalculation)
17. [احراز هویت (OAuth 2.0)](#۱۷-احراز-هویت-oauth-20)
18. [راهنمای استفاده از API با GraphQL](#۱۸-راهنمای-استفاده-از-api-با-graphql)
19. [تراکنش‌ها در API (Query)](#۱۹-تراکنش‌ها-در-api)
20. [حساب بانکی در API](#۲۰-حساب-بانکی-در-api)
21. [درگاه‌ها (Terminal) در API](#۲۱-درگاه‌ها-در-api)
22. [نمونه کد Python (SDK)](#۲۲-نمونه-کد-python)
23. [سرویس MCP زرین‌پال](#۲۳-سرویس-mcp-زرینپال)
24. [جمع‌بندی مراحل پیاده‌سازی](#۲۴-جمعبندی-مراحل-پیادهسازی)
25. [نکات و ناهماهنگی‌های مستندات](#۲۵-نکات-و-ناهماهنگیهای-مستندات)

---

## ۱. معرفی درگاه پرداخت

این سرویس امکان پرداخت الکترونیک در محیط وب را برای فروشگاه‌های اینترنتی فراهم می‌کند. پرداخت از طریق **وب‌سرویس** و روی **پروتکل امن HTTPS** انجام می‌شود و خریداران می‌توانند با کارت‌های عضو شبکه شتاب پرداخت کنند.

محدوده این مستند شامل موارد زیر است:

- شرح کلی عملیات لازم برای درخواست پرداخت از سوی پذیرنده روی درگاه پرداخت اینترنتی زرین‌پال
- شرح تمام متدهای مربوط به این عملیات

همه داده‌های برگشتی از زرین‌پال به صورت **JSON** هستند.

---

## ۲. واژگان

| واژه | تعریف |
|---|---|
| **پذیرنده** | شخص، سازمان یا شرکتی که محصول یا سرویسی را در بستر اینترنت ارائه می‌کند. |
| **خریدار** | دارنده کارت‌های بانکی عضو شبکه شتاب که قصد خرید اینترنتی از پذیرنده را دارد. |
| **تراکنش** | یک عملیات مالی؛ در این مستند مصداق آن یک خرید اینترنتی است. |

---

## ۳. اطلاعات فنی سیستم

| عنوان | توضیح |
|---|---|
| **`merchant_id` (کد درگاه پرداخت)** | کدی یکتا و ۳۶ کاراکتری (فرمت UUID) که زرین‌پال به ازای هر درگاه به پذیرنده اختصاص می‌دهد. |
| **آدرس IP پذیرنده** | آدرس IP سرور اصلی وب‌سایت پذیرنده. پذیرنده باید از طریق ورود به قسمت **افزونه‌ها ← نمونه کدها ← فایل‌ها و آموزش‌ها** IP صحیح را دریافت و در پنل زرین‌پال ثبت کند. این IP برای متدهای ریورس و سایر محدودیت‌های امنیتی لازم است. |
| **`Authority` (شناسه مرجع)** | شناسه یکتای هر درخواست پرداخت که زرین‌پال پس از ثبت درخواست برمی‌گرداند. از نوع UUID با طول ۳۶ کاراکتر و رشته‌ای است که با حرف **A** شروع می‌شود. |
| **`Code` (وضعیت)** | عددی که وب‌سرویس زرین‌پال به عنوان وضعیت تراکنش برمی‌گرداند (جدول کدها در بخش ۷). |
| **`ref_id` (شماره تراکنش خرید)** | شناسه یکتایی که پس از تکمیل موفق تراکنش صادر می‌شود و برای پیگیری‌های مالی استفاده می‌شود. |
| **`description` (توضیحات تراکنش)** | متن خلاصه‌ای که پذیرنده برای معرفی کالا یا خدمات می‌نویسد. حداکثر ۵۰۰ کاراکتر. |
| **`mobile` (شماره تماس خریدار)** | اختیاری. برای سهولت پیگیری‌های پس از پرداخت. |
| **`email` (ایمیل خریدار)** | اختیاری. برای سهولت پیگیری‌های پس از پرداخت. |
| **`callback_url` (آدرس بازگشت)** | آدرسی که پس از پایان عملیات در سمت زرین‌پال، خریدار به آن بازگردانده می‌شود. |

---

## ۴. نیازمندی‌های امنیتی

- **SSL زرین‌پال:** وب‌سایت زرین‌پال گواهینامه SSL معتبر دارد؛ بنابراین ارتباط خریدار با زرین‌پال و ارتباط پذیرنده با زرین‌پال در بستر SSL انجام می‌شود.
- **SSL پذیرنده:** داشتن گواهینامه SSL معتبر برای پذیرنده **اجباری نیست**، اما در صورت داشتن آن، ارتباط بین خریدار و پذیرنده نیز امن خواهد بود. داشتن آن به نفع خریدار و پذیرنده است.
- **عدم دریافت اطلاعات مالی:** پذیرنده و زرین‌پال نباید از هیچ‌یک از اطلاعات مالی خریدار (شماره کارت، رمز کارت، میزان موجودی و...) مطلع شوند. پذیرنده هیچ اطلاعات مالی یا بانکی از خریدار دریافت نمی‌کند و تمام این اطلاعات مستقیماً توسط خریدار در **درگاه پرداخت** وارد می‌شود.

---

## ۵. راهنمای اتصال به درگاه

### مرحله ۱: ارسال اطلاعات اولیه (Payment Request)

پذیرنده پارامترهای زیر را با متد **`POST`** و با فرمت JSON به آدرس درخواست پرداخت ارسال می‌کند:

```
https://payment.zarinpal.com/pg/v4/payment/request.json
```

| نام | نوع | الزام | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری اختصاصی پذیرنده |
| `amount` | Integer | بله | مبلغ تراکنش |
| `currency` | String | خیر | تعیین واحد پولی: ریال (`IRR`) یا تومان (`IRT`) |
| `description` | String | بله | توضیحات مربوط به تراکنش |
| `callback_url` | String | بله | صفحه بازگشت مشتری پس از انجام پرداخت |
| `referrer_id` | String | خیر | کد معرف |
| `metadata` | Array/Object | خیر | شامل مقادیر `mobile`، `email`، `order_id` و در موارد خاص `card_pan` و `auto_verify` |
| `mobile` | String | خیر | شماره تماس خریدار |
| `email` | String | خیر | ایمیل خریدار |
| `order_id` | String | خیر | شماره سفارش |

#### نمونه درخواست (cURL)

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": 1000,
  "callback_url": "http://your-site.com/verify",
  "referrer_id": "xxxx",
  "description": "Transaction description.",
  "metadata": {"mobile": "09121234567","email": "info.test@gmail.com"}
}'
```

#### نمونه درخواست (PHP با cURL)

```php
<?php
$curl = curl_init();
curl_setopt_array($curl, array(
  CURLOPT_URL => 'https://payment.zarinpal.com/pg/v4/payment/request.json',
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_ENCODING => '',
  CURLOPT_MAXREDIRS => 10,
  CURLOPT_TIMEOUT => 0,
  CURLOPT_FOLLOWLOCATION => true,
  CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
  CURLOPT_CUSTOMREQUEST => 'POST',
  CURLOPT_POSTFIELDS =>'{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": "1100",
  "callback_url": "http://example.com/verify",
  "referrer_id": "xxxx",
  "description": "Transaction description.",
  "metadata": {
    "mobile": "09121234567",
    "email": "info.test@example.com"
  }
}',
  CURLOPT_HTTPHEADER => array(
    'Content-Type: application/json',
    'Accept: application/json'
  ),
));
$response = curl_exec($curl);
curl_close($curl);
echo $response;
```

#### پاسخ موفق

```json
{
  "data": {
    "code": 100,
    "message": "Success",
    "authority": "A0000000000000000000000000000wwOGYpd",
    "fee_type": "Merchant",
    "fee": 100
  },
  "errors": []
}
```

اگر `code` برابر `100` و `authority` دریافت شد، اطلاعات ارسالی صحیح بوده و باید به مرحله بعد بروید.

### مرحله ۲: انتقال خریدار به صفحه پرداخت

مقدار `authority` دریافتی را در انتهای آدرس درگاه پرداخت قرار دهید و خریدار را به آن URL ریدایرکت کنید. خریدار بلافاصله به درگاه بانکی هدایت می‌شود و مراحل پرداخت را انجام می‌دهد.

> در پیاده‌سازی Python SDK این آدرس با متد `generate_payment_url(authority)` ساخته می‌شود (بخش ۲۲).

### مرحله ۳: بازگشت به وب‌سایت پذیرنده

پس از پایان عملیات در سمت زرین‌پال، خریدار به `callback_url` بازمی‌گردد. زرین‌پال یک پارامتر **`Status`** را در QueryString ارسال می‌کند که دو مقدار ثابت دارد:

| مقدار Status | معنی |
|---|---|
| `OK` | پرداخت موفق بوده؛ باید متد **verify** فراخوانی شود. |
| `NOK` | تراکنش ناموفق بوده یا توسط خریدار لغو شده است؛ **متد verify نباید فراخوانی شود**. |

### مرحله ۴: اعتبارسنجی (Verify)

فقط در صورتی که `Status=OK` باشد، متد **verify** را فراخوانی کنید.

- اگر `code` برابر `100` باشد، تراکنش موفق است و می‌توانید `ref_id` را به کاربر نمایش دهید.
- در غیر این صورت، با توجه به کد خطای دریافتی، کاربر را از خطا آگاه کنید.

#### پارامترهای ارسالی به Verify

| نام | نوع | توضیحات |
|---|---|---|
| `merchant_id` | String | کد ۳۶ کاراکتری اختصاصی پذیرنده |
| `amount` | Integer | مبلغ تراکنش (ریال) |
| `authority` | String | کد یکتای شناسه مرجع درخواست |

#### پارامترهای برگشتی از Verify

| نام | نوع | توضیحات |
|---|---|---|
| `code` | Integer | عددی که موفق بودن یا نبودن پرداخت را نشان می‌دهد |
| `ref_id` | Integer | در صورت موفقیت، شماره تراکنش پرداخت |
| `card_pan` | String | شماره کارت به صورت Mask (مثلاً `502229******5995`) |
| `card_hash` | String | هش کارت با الگوریتم SHA256 |
| `fee_type` | String | پرداخت‌کننده کارمزد (`Merchant` یا `Payer`) که در پنل قابل تنظیم است |
| `fee` | Integer | کارمزد |

#### نمونه درخواست Verify (cURL)

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/verify.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
"merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "amount": 1000,
        "authority": "A0000000000000000000000000000wwOGYpd"
}'
```

#### نمونه درخواست Verify (PHP)

```php
<?php
$curl = curl_init();
curl_setopt_array($curl, array(
  CURLOPT_URL => 'https://payment.zarinpal.com/pg/v4/payment/verify.json',
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_ENCODING => '',
  CURLOPT_MAXREDIRS => 10,
  CURLOPT_TIMEOUT => 0,
  CURLOPT_FOLLOWLOCATION => true,
  CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
  CURLOPT_CUSTOMREQUEST => 'POST',
  CURLOPT_POSTFIELDS =>'{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": "1000",
  "authority": "A0000000000000000000000000000wwOGYpd"
}',
  CURLOPT_HTTPHEADER => array(
    'Content-Type: application/json',
    'Accept: application/json'
  ),
));
$response = curl_exec($curl);
curl_close($curl);
echo $response;
```

#### پاسخ موفق Verify

```json
{
  "data": {
    "code": 100,
    "message": "Verified",
    "card_hash": "1EBE3EBEBE35C7EC0F8D6EE4F2F859107A87822CA179BC9528767EA7B5489B69",
    "card_pan": "502229******5995",
    "ref_id": 201,
    "fee_type": "Merchant",
    "fee": 0
  },
  "errors": []
}
```

#### نکته مهم درباره کد ۱۰۱

- با اولین فراخوانی موفق verify، کد **100** برمی‌گردد.
- در فراخوانی‌های بعدی همان تراکنش، کد **101** برمی‌گردد که یعنی تراکنش قبلاً وریفای شده است.
- کد 101 خطا نیست؛ به معنای موفق بودن تراکنش و انجام یک‌بار verify روی آن است.

---

## ۶. سرویس تست (Sandbox)

برای تست بدون پرداخت مبلغ واقعی، پس از پیاده‌سازی، آدرس وب‌سرویس‌ها را تغییر دهید:

```
https://payment.zarinpal.com/...   ←  تغییر به  →   https://sandbox.zarinpal.com/...
```

**نکات:**

- تمام `authority`های دریافتی از سندباکس با حرف **S** شروع می‌شوند.
- در سرویس تست، برای فیلد `merchant_id` می‌توانید **یک رشته UUID دلخواه** (مثلاً از یک ژنراتور UUID نسخه ۴) وارد کنید.

---

## ۷. لیست خطاها و کدهای وضعیت

### کدهای عمومی (public)

| کد | پیام انگلیسی | شرح فارسی و راهکار |
|---|---|---|
| **-9** | Validation error | خطای اعتبارسنجی. علت‌ها: ۱) `merchant_id` وارد نشده؛ ۲) `callback_url` وارد نشده؛ ۳) `description` وارد نشده یا بیش از ۵۰۰ کاراکتر است؛ ۴) مبلغ کمتر یا بیشتر از حد مجاز است؛ ۵) `referrer_id` نامعتبر است. |
| **-10** | Terminal is not valid, please check merchant_id or ip address. | IP یا مرچنت‌کد پذیرنده صحیح نیست. |
| **-11** | Terminal is not active, please contact our support team. | مرچنت‌کد فعال نیست. پذیرنده باید به امور مشتریان زرین‌پال مراجعه کند. |
| **-12** | Too many attempts, please try again later. | تلاش‌ها بیش از حد مجاز در بازه زمانی کوتاه است. بعداً دوباره تلاش کنید. |
| **-13** | terminal limit reached. | محدودیت تراکنش. برای رفع آن باید مدارک تکمیل شود (از طریق پشتیبانی). |
| **-14** | The callback URL domain does not match the registered terminal domain. | دامنه `callback_url` با دامنه ثبت‌شده درگاه مغایرت دارد. |
| **-15** | Terminal user is suspend | درگاه به حالت تعلیق درآمده. باید به امور مشتریان ارجاع شود. |
| **-16** | Terminal user level is not valid | سطح تأیید پذیرنده پایین‌تر از سطح **نقره‌ای** است. |
| **-17** | Terminal user level is not valid | محدودیت پذیرنده در **سطح آبی**. |
| **-18** | The referrer address does not match the registered domain. | امکان استفاده از کد درگاه اختصاصی روی سایت یا جای دیگر وجود ندارد. |
| **-19** | Terminal user transactions are banned. | ایجاد تراکنش برای این ترمینال امکان‌پذیر نیست. |
| **100** | Success | عملیات موفق. |

### کدهای درخواست پرداخت (PaymentRequest)

| کد | پیام انگلیسی | شرح |
|---|---|---|
| **-40** | Invalid extra params, expire_in is not valid. | پارامتر اضافی نامعتبر؛ `expire_in` صحیح نیست. |
| **-41** | Maximum amount is 100,000,000 tomans. | حداکثر مبلغ پرداختی **۱۰۰ میلیون تومان** است. |

### کدهای اعتبارسنجی (PaymentVerify)

| کد | پیام انگلیسی | شرح |
|---|---|---|
| **-50** | Session is not valid, amounts values is not the same. | مبلغ پرداخت‌شده با مبلغ ارسالی در متد verify متفاوت است. |
| **-51** | Session is not valid, session is not active paid try. | پرداخت ناموفق. |
| **-52** | Oops!!, please contact our support team | خطای غیرمنتظره. باید به پشتیبانی ارجاع شود. |
| **-53** | Session is not this merchant_id session | پرداخت متعلق به این مرچنت‌کد نیست. |
| **-54** | Invalid authority. | اتوریتی نامعتبر است. |
| **-55** | manual payment request not found. | تراکنش موردنظر یافت نشد. |
| **101** | Verified | تراکنش قبلاً وریفای شده است (در فراخوانی‌های بعدی). |

### کدهای ریورس (PaymentReverse)

| کد | پیام انگلیسی | شرح |
|---|---|---|
| **-60** | Session can not be reversed with bank. | امکان ریورس این تراکنش با بانک وجود ندارد. |
| **-61** | Session is not in success status. | تراکنش موفق نیست یا قبلاً ریورس شده است. |
| **-62** | Terminal ip limit must be active. | IP سرور برای درگاه تنظیم نشده است. |
| **-63** | Maximum time for reverse this session is expired. | مهلت ۳۰ دقیقه‌ای ریورس تمام شده است. |

### کد ۶۱- و ۶۲- و کدهای دیگر

- کد **62-** در بخش ریورس به معنای نبودن IP سرور در تنظیمات درگاه است.
- کد **-31** در بخش MCP ذکر شده است؛ در جدول خطاهای این مستند ذکری از آن نیست و باید در صورت نیاز از پشتیبانی یا ابزار `get_error_code` بررسی شود.

---

## ۸. اعتبارسنجی تراکنش (خودکار/غیرخودکار)

### مفهوم

پس از اینکه خریدار پرداخت را در درگاه بانکی انجام می‌دهد، زرین‌پال باید از بانک (PSP) استعلام و تأیید بگیرد تا موفقیت نهایی تراکنش مطمئن شود. این مرحله **Verify نهایی** نام دارد.

- تا زمانی که Verify انجام نشود، پرداخت کامل تلقی نمی‌شود.
- اگر این مرحله در بازه زمانی مقرر انجام نشود، **مبلغ به حساب خریدار بازگردانده می‌شود**.

### تنظیم در پنل

- **اعتبارسنجی خودکار فعال:** زرین‌پال پس از پرداخت موفق، خودکار نزد بانک Verify می‌کند.
- **اعتبارسنجی غیرخودکار:** شروع Verify با پذیرنده است و باید با فراخوانی متد verify آغاز شود.

### پارامتر `metadata.auto_verify`

برای کنترل دقیق‌تر در لحظه پرداخت، می‌توانید پارامتر اختیاری `auto_verify` را در `metadata` ارسال کنید.

| مقدار ارسالی | رفتار |
|---|---|
| **`true`** | تراکنش پس از پرداخت موفق به‌صورت خودکار Verify می‌شود، حتی اگر در پنل خودکار غیرفعال باشد. نیازی به فراخوانی verify از سمت پذیرنده نیست. |
| **`false`** | Verify خودکار انجام نمی‌شود. زرین‌پال فقط زمانی Verify می‌کند که پذیرنده متد verify را فراخوانی کند. اگر فراخوانی در بازه مجاز انجام نشود، تراکنش نهایی نشده و مبلغ برمی‌گردد. |
| **ارسال نشود** | رفتار بر اساس تنظیم پنل تعیین می‌شود. |

**موارد کاربرد:**

- برای تراکنش‌های با مبلغ یا ریسک بالا، Verify غیرخودکار اعمال کنید.
- برای پرداخت‌های روتین، Verify خودکار فعال کنید.
- در صورت احتمال اختلال در سایت پذیرنده یا عدم رسیدن خریدار به `callback_url`، کنترل کامل Verify را با `auto_verify=false` به خود پذیرنده بسپارید تا از مغایرت بین سیستم پذیرنده و زرین‌پال جلوگیری شود.

> در صورت ارسال این پارامتر، مقدار `metadata.auto_verify` همواره نسبت به تنظیمات پنل اولویت دارد.

#### نمونه درخواست با auto_verify

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "currency": "IRT",
  "amount": 10000,
  "callback_url": "https://example.com/payment-callback",
  "description": "خرید اشتراک",
  "metadata": {
    "auto_verify": true,
    "mobile": "09121234567",
    "email": "info@example.com"
  }
}'
```

---

## ۹. میان‌پی (صفحه چک‌اوت)

با پارامتر اختیاری **`cart_data`** می‌توانید جزئیات سبد خرید را هنگام ایجاد تراکنش ارسال کنید. این کار اختیاری است، اما توصیه می‌شود تا فرایند پرداخت برای خریدار شفاف‌تر شود.

`cart_data` از سه بخش تشکیل شده است: `items`، `added_costs` و `deductions`.

### بخش `items` (آرایه محصولات)

| نام | نوع | الزام | توضیحات |
|---|---|---|---|
| `item_name` | String | بله | نام محصول یا خدمت |
| `item_amount` | String | بله | مبلغ هر واحد به ریال |
| `item_count` | String | بله | تعداد واحدها |
| `item_amount_sum` | String | بله | مجموع مبلغ (`item_amount × item_count`). **این مقدار را پذیرنده باید محاسبه و ارسال کند.** |

### بخش `added_costs` (هزینه‌های اضافی؛ همه اختیاری)

| نام | نوع | توضیحات |
|---|---|---|
| `tax` | String | مالیات بر سبد خرید (ریال) |
| `payment` | String | کارمزد یا هزینه پرداخت (ریال) |
| `transport` | String | هزینه حمل و نقل یا ارسال (ریال) |

### بخش `deductions` (کسر و تخفیف؛ همه اختیاری)

| نام | نوع | توضیحات |
|---|---|---|
| `discount` | String | مبلغ تخفیف که از مجموع سبد کم می‌شود (ریال) |

### نمونه کامل

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": 150000,
  "description": "پرداخت مربوط به سفارش شماره 1010 در فروشگاه تستی",
  "metadata": {
    "mobile": "09120000000",
    "email": "user@example.com",
    "order_id": "1234567890",
    "card_pan": "502229XXXXXX1234"
  },
  "cart_data": {
    "items": [
      {
        "item_name": "کفش ورزشی نایک",
        "item_amount": 50000,
        "item_count": 2,
        "item_amount_sum": 100000
      },
      {
        "item_name": "جوراب اسپرت",
        "item_amount": 25000,
        "item_count": 1,
        "item_amount_sum": 25000
      }
    ],
    "added_costs": {
      "tax": 5000,
      "payment": 1000,
      "transport": 2000
    },
    "deductions": {
      "discount": 3000
    }
  },
  "callback_url": "https://example.com/payment/verify"
}'
```

**بررسی مبلغ در مثال بالا:** مجموع اقلام ۱۲۵٬۰۰۰ + مالیات ۵٬۰۰۰ + کارمزد ۱٬۰۰۰ + حمل ۲٬۰۰۰ − تخفیف ۳٬۰۰۰ = **۱۳۰٬۰۰۰ ریال**. توجه: مبلغ `amount` در این مثال ۱۵۰٬۰۰۰ است؛ پذیرنده باید مطمئن شود که `amount` با جمع نهایی سبد هماهنگ است.

---

## ۱۰. واحد پولی

- پارامتر `currency` تعیین می‌کند مبلغ بر حسب کدام واحد است.
  - **`IRR`** = ریال (پیش‌فرض)
  - **`IRT`** = تومان
- در مستندات، مبلغ در بیشتر متدها **به ریال** تعریف شده است. اگر از `IRT` استفاده می‌کنید، مبلغ را با واحد تومان ارسال کنید و `currency` را صریحاً `IRT` قرار دهید.
- در متد **FeeCalculation** نیز پارامتر `currency` با مقادیر مجاز `IRR` و `IRT` وجود دارد.
- در بخش همکاری در فروش، `currency` اختیاری است.

> نمونه `currency: "IRT"` در مستندات اعتبارسنجی خودکار و همکاری در فروش آمده است.

---

## ۱۱. پرداخت با کارت مشخص و ذخیره کارت

### پرداخت با کارت مشخص (`card_pan`)

با این سرویس، خریدار **تنها** با کارتی پرداخت می‌کند که قبلاً توسط پذیرنده احراز شده و مورد تأیید است.

- برای اینکه تراکنش با کارت دیگری ناموفق شود، شماره کارت را در قسمت `metadata` با نام **`card_pan`** ارسال کنید.

| نام | نوع | الزام | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |
| `amount` | Integer | بله | مبلغ (ریال) |
| `description` | String | بله | توضیحات تراکنش |
| `callback_url` | String | بله | صفحه بازگشت مشتری |
| `referrer_id` | String | خیر | کد معرف |
| `metadata` | Array | خیر | شامل `mobile`، `email` و `card_pan` |
| `mobile` | String | خیر | شماره تماس خریدار |
| `email` | String | خیر | ایمیل خریدار |
| `card_pan` | Integer | خیر | شماره کارت پرداخت‌کننده |

#### نمونه درخواست

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": 10000,
  "callback_url": "http://yoursite.com/verify",
  "description": "پرداخت تست ۱۱۰",
  "referrer_id": "xxxx",
  "metadata": {"mobile": "09121234567","email": "info.test@gmail.com", "card_pan":"5022291912345678"}
}'
```

> **توجه:** در نمونه اصلی مستندات، پس از `"card_pan"` کاما وجود دارد که JSON معتبر نیست. در ارسال واقعی، کاما انتهایی را حذف کنید.

#### پاسخ Verify در این حالت

```json
{
  "data": {
    "code": 100,
    "message": "Verified",
    "card_hash": "1EBE3EZSZF35C7EC0F8D6EE4F2F859107A87822CA179BC9528767EA7B5489B69",
    "card_pan": "502229******1234",
    "ref_id": 201,
    "fee_type": "Merchant",
    "fee": 0
  },
  "errors": []
}
```

### ذخیره کارت در درگاه (Card Save)

- وقتی خریدار برای اولین بار وارد درگاه می‌شود، اطلاعات کامل کارت (شماره ۱۶ رقمی، CVV2 و تاریخ انقضا) و کد امنیتی را وارد می‌کند و سپس رمز پویای پیامکی را دریافت و تأیید می‌کند.
- اگر پذیرنده **شماره موبایل خریدار** را ارسال کند، زرین‌پال آن را به بانک عامل می‌فرستد و اطلاعات کارت مرتبط با آن شماره ذخیره می‌شود.
- در پرداخت‌های بعدی با همان شماره موبایل، کارت‌های ذخیره‌شده برای انتخاب نمایش داده می‌شوند و خریدار تنها **CVV2** را وارد می‌کند.
- **مزیت‌ها:** سرعت بیشتر پرداخت، تجربه بهتر کاربر، کاهش خطای ورود اطلاعات و افزایش نرخ پرداخت موفق.
- **پیش‌نیاز:** پذیرنده باید پارامتر `mobile` خریدار را دریافت و ارسال کند.
- بقیه مراحل مانند [راهنمای اتصال](#۵-راهنمای-اتصال-به-درگاه) است.

#### نمونه درخواست

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "amount": 10000,
  "callback_url": "http://yoursite.com/verify",
  "description": "افزایش اعتبار کاربر شماره ۱۱۳۴۶۲۹",
  "referrer_id": "xxxx",
  "metadata": {"mobile": "09121234567","email": "info.test@gmail.com"}
}'
```

---

## ۱۲. ریورس تراکنش

ریورس، تراکنش‌های **موفق** را که کمتر از **۳۰ دقیقه** از پرداخت آن‌ها گذشته، **بدون کارمزد** و سریع به حساب خریدار برمی‌گرداند.

- برای استعلام وضعیت تراکنش در ۳۰ دقیقه اول، از متد [استعلام وضعیت پرداخت](#۱۵-استعلام-وضعیت-پرداخت) استفاده کنید.
- **شرط حیاتی:** IP سرور شما باید برای درگاه تنظیم شده باشد؛ در غیر این صورت خطای **-62** دریافت می‌کنید. تنظیم IP از بخش تنظیمات درگاه انجام می‌شود.

#### ورودی

| نام | نوع | اجباری | شرح |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |
| `authority` | String | بله | آتوریتی تراکنش موردنظر |

#### خروجی

| نام | نوع | شرح |
|---|---|---|
| `code` | Integer | عدد نشان‌دهنده موفقیت یا عدم موفقیت |
| `message` | String | `Reversed` یعنی درخواست موفق بوده |
| `errors` | Array | در صورت خطا، کد و پیام آن |

#### نمونه پاسخ موفق

```json
{
  "data": {
    "code": 100,
    "message": "Reversed"
  },
  "errors": []
}
```

#### نمونه درخواست

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/reverse.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "authority": "A000000000000000000000000000xpgr85j5"
}'
```

#### نمونه خطاها

```json
{ "data": {}, "errors": { "message": "Session can not be reversed with bank.", "code": -60, "validations": [] } }
```
```json
{ "data": {}, "errors": { "message": "Session is not in success status.", "code": -61, "validations": [] } }
```
```json
{ "data": {}, "errors": { "message": "Terminal ip limit most be active.", "code": -62, "validations": [] } }
```
```json
{ "data": {}, "errors": { "message": "Maximum time for reverse this session is expired.", "code": -63, "validations": [] } }
```

---

## ۱۳. همکاری در فروش (referrer_id)

با پارامتر `referrer_id` می‌توانید از تراکنش‌های زیرمجموعه‌های خود سهم دریافت کنید.

**شروع کار:**

1. داشتن حساب کاربری زرین‌پال
2. دریافت لینک همکاری از پنل کاربری (بخش referral)
3. اطلاعات بیشتر در صفحه رسمی همکاری در فروش زرین‌پال

#### پارامترها

| نام | نوع | الزام | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |
| `currency` | String | خیر | واحد پولی |
| `amount` | Integer | بله | مبلغ تراکنش |
| `description` | String | بله | توضیحات تراکنش |
| `callback_url` | String | بله | صفحه بازگشت پذیرنده |
| `referrer_id` | String | خیر | کد معرف |
| `metadata` | Array | خیر | ... |
| `mobile` | String | خیر | شماره تماس خریدار |
| `email` | String | خیر | ایمیل خریدار |

#### خطاهای referrer_id

| کد | توضیح خطا | نحوه برخورد سیستم |
|---|---|---|
| **429** | قالب کد معرف معتبر نیست | درخواست رد می‌شود و خطا مستقیم برگردانده می‌شود. |
| — | خطای رمزگشایی شناسه (Invalid decoding) | `referrer_id` پردازش نمی‌شود و در تراکنش ذخیره نمی‌شود. |
| — | کاربر معرف یافت نشد | `referrer_id` پردازش نمی‌شود و ذخیره نمی‌شود. |
| — | ترمینال متعلق به معرف است | `referrer_id` پردازش نمی‌شود و ذخیره نمی‌شود. |
| — | ترمینال از قبل دارای معرف است | `referrer_id` پردازش نمی‌شود و ذخیره نمی‌شود. |

> در چهار حالت آخر، درخواست رد نمی‌شود؛ فقط `referrer_id` نادیده گرفته می‌شود. بنابراین بررسی کنید که معرف ذخیره شده باشد.

#### نمونه درخواست

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/request.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "currency": "IRT",
  "amount": 10000,
  "callback_url": "http://example.com/verify",
  "description": "افزایش اعتبار کاربر شماره ۱۱۳۴۶۲۹",
  "referrer_id": "xxxx",
  "metadata": {"mobile": "09121234567","email": "info.test@gmail.com"}
}'
```

---

## ۱۴. متد unVerified

این متد برای زمانی است که بخواهید پرداخت‌های **موفقی** را پیدا کنید که توسط وب‌سرویس درست انجام شده‌اند، اما متد verify روی آن‌ها اعمال نشده است.

- **آدرس:** `https://payment.zarinpal.com/pg/v4/payment/unVerified.json`
- **ورودی:** `merchant_id` (اجباری)
- **خروجی:**
  - `code`: وضعیت عملیات
  - `authorities`: آرایه‌ای JSON شامل `authority`، `amount`، `callback_url`، `referer` و `date` (نوع درگاه و زمان پرداخت)
- **محدودیت:** حداکثر **۱۰۰ تراکنش آخر** که Verify نشده‌اند بازگردانده می‌شود.

#### نمونه پاسخ

```json
{
  "data": {
    "code": "100",
    "message": "Success",
    "authorities": [
      {
        "authority": "A0000000000000000000000000000wwOGYpd",
        "amount": 50500,
        "callback_url": "https://test.com/vpay",
        "referer": "https://example.com/test-form/",
        "date": "2020-07-01 17:33:25"
      },
      {
        "authority": "A00000000000000000000000000207296508",
        "amount": 50500,
        "callback_url": "https://test.com/vpay",
        "referer": "https://example.com/test-form/",
        "date": "2020-07-01 18:58:32"
      },
      {
        "authority": "A00000000000000000000000000206875420",
        "amount": 11100,
        "callback_url": "zarin_link",
        "referer": "/",
        "date": "2020-06-27 10:22:02"
      }
    ]
  }
}
```

---

## ۱۵. استعلام وضعیت پرداخت

این متد **فقط وضعیت** یک تراکنش را اعلام می‌کند.

> **هشدار:** از این متد **هرگز** برای تأیید و Verify کردن تراکنش استفاده نکنید.

- **آدرس:** `https://payment.zarinpal.com/pg/v4/payment/inquiry.json`
- **ورودی:** `merchant_id` و `authority` (هر دو اجباری)

#### وضعیت‌های ممکن (`status`)

| وضعیت | معنی |
|---|---|
| `VERIFIED` | وریفای‌شده |
| `PAID` | پرداخت‌شده ولی وریفای‌نشده |
| `IN_BANK` | در حال پرداخت |
| `FAILED` | ناموفق (تکمیل نشده) |
| `REVERSED` | ریورس‌شده |

#### نمونه پاسخ موفق

```json
{
  "data": {
    "status": "PAID",
    "code": 100,
    "message": "Success"
  },
  "errors": []
}
```

#### نمونه پاسخ ناموفق (authority اشتباه)

```json
{
  "message": "Invalid authority",
  "errors": {
    "authority": [
      "Invalid authority.",
      "-54"
    ]
  }
}
```

#### نمونه درخواست

```sh
curl -X POST \
  https://payment.zarinpal.com/pg/v4/payment/inquiry.json \
  -H 'accept: application/json' \
  -H 'content-type: application/json' \
  -d '{
  "merchant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "authority": "A000000000000000000000000000xpgr85j5"
}'
```

---

## ۱۶. محاسبه کارمزد (FeeCalculation)

این متد **قبل** از ایجاد درخواست پرداخت کارمزد را محاسبه می‌کند؛ مفید برای نمایش کارمزد به کاربر یا لحاظ آن در محاسبات. این متد **هیچ تراکنشی ایجاد نمی‌کند**.

- **آدرس:** `https://payment.zarinpal.com/pg/v4/payment/feeCalculation.json`

#### ورودی

| نام | نوع | الزامی | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |
| `amount` | Number | بله | مبلغ به ریال، **حداقل ۱۰۰۰ ریال** |
| `currency` | String | خیر | `IRR` (پیش‌فرض) یا `IRT` |

#### خروجی

| نام | نوع | توضیحات |
|---|---|---|
| `code` | Number | ۱۰۰ یعنی موفق |
| `message` | String | پیام وضعیت |
| `amount` | Number | مبلغ اصلی تراکنش (ریال) |
| `fee` | Number | کارمزد محاسبه‌شده (ریال) |
| `fee_type` | String | `Merchant` (پذیرنده می‌پردازد) یا `Payer` (مشتری می‌پردازد) |
| `suggested_amount` | String | مبلغ پیشنهادی برای تسویه حساب |

#### نمونه درخواست

```bash
curl -X POST https://payment.zarinpal.com/pg/v4/payment/feeCalculation.json \
-H "Content-Type: application/json" \
-H "Accept: application/json" \
-d '{
  "merchant_id": "Your merchant code",
  "amount": 100000,
  "currency": "IRR"
}'
```

#### نمونه پاسخ موفق

```json
{
  "data": {
    "amount": 100000,
    "fee": 4200,
    "fee_type": "Merchant",
    "suggested_amount": 104329,
    "code": 100,
    "message": "Success"
  },
  "errors": []
}
```

#### نکات مهم

- مبلغ تراکنش باید حداقل ۱۰۰۰ ریال باشد.
- کارمزد بر اساس تنظیمات ترمینال و نوع تراکنش متفاوت است.
- `fee_type` می‌تواند `Merchant` یا `Payer` باشد.

---

## ۱۷. احراز هویت (OAuth 2.0)

احراز هویت در پنل زرین‌پال با **OAuth 2.0** و استاندارد **REST** انجام می‌شود. قبل از شروع باید `client_id` و `client_secret` را از پشتیبانی زرین‌پال دریافت کنید.

> همه درخواست‌های این بخش **POST** با فرمت `application/json` هستند.

### مرحله ۱: ثبت نام (Register)

- **آدرس:** `https://next.zarinpal.com/api/oauth/register`

| نام | نوع | الزامی | توضیحات |
|---|---|---|---|
| `first_name` | string | بله | نام |
| `last_name` | string | بله | نام خانوادگی |
| `cell_number` | Integer | بله | شماره تلفن همراه |

```sh
curl 'https://next.zarinpal.com/api/oauth/register' \
  -H 'Content-Type: application/json' \
  --data-binary '{"first_name": "علی","last_name": "علیپور","cell_number":"09123456789"}'
```

**پاسخ (در صورت ثبت‌نام جدید):**

```json
{
    "user_id": 945298
}
```

> اگر کاربر قبلاً ثبت‌نام کرده باشد، خطای «موجود بودن» دریافت می‌شود.

### مرحله ۲: شروع کار (Initialize)

- **آدرس:** `https://next.zarinpal.com/api/oauth/initialize`

| نام | نوع | الزامی | پیش‌فرض | توضیحات |
|---|---|---|---|---|
| `username` | string | بله | — | ایمیل یا شماره همراه کاربر |
| `channel` | string (`ussd` یا `sms`) | خیر | `ussd` | کانال دریافت رمز یک‌بار مصرف |

```sh
curl 'https://next.zarinpal.com/api/oauth/initialize' \
  -H 'Content-Type: application/json' \
  --data-binary '{"username":"09123456789","channel":"ussd"}'
```

```bash
curl -X POST \
  https://next.zarinpal.com/api/oauth/initialize \
  -H 'content-type: application/json' \
  -d '{"username":"09123456789","channel":"sms"}'
```

**پاسخ:**

```json
{
  "avatar": "https:\/\/gravatar.com\/avatar\/{EMAIL_HASH}",
  "channel": "ussd",
  "ussd_code": "*733*4*97*2#",
  "waiting_time": 120,
  "otp_time_diff": 900
}
```

| نام | نوع | توضیحات |
|---|---|---|
| `avatar` | string | آدرس آواتار (معمولاً Gravatar) |
| `channel` | string | کانالی که رمز از طریق آن ارسال شده |
| `ussd_code` | string | کد USSD برای دریافت رمز؛ اگر `channel=sms` باشد، خالی است |
| `waiting_time` | int | زمان انتظار (ثانیه) تا درخواست مجدد رمز |
| `otp_time_diff` | int | (در مستندات با عنوان @todo آمده است) |

### مرحله ۳: تأیید رمز و دریافت توکن (Verification)

پس از وارد کردن رمز یک‌بار مصرف، یک **Access Token** و یک **Refresh Token** دریافت می‌کنید.

- **آدرس:** `https://next.zarinpal.com/api/oauth/token`

| نام | نوع | الزامی | پیش‌فرض | توضیحات |
|---|---|---|---|---|
| `grant_type` | string | بله | `password` | در این مرحله باید `password` باشد |
| `client_id` | int | بله | — | آی‌دی کلاینت دریافتی از زرین‌پال |
| `client_secret` | string | بله | — | کلید کلاینت دریافتی از زرین‌پال |
| `username` | string | بله | — | ایمیل یا موبایل کاربر |
| `password` | string | بله | — | رمز یک‌بار مصرفی که کاربر وارد کرده |
| `scope` | string | بله | `*` | (در مستندات با عنوان @todo آمده است) |

```sh
curl 'https://next.zarinpal.com/api/oauth/token' \
  -H 'Content-Type: application/json' \
  --data-binary '{
    "grant_type": "password",
    "client_id": 100,
    "client_secret": "$ecreT",
    "username": "09123456789",
    "password": "12345678",
    "scope": "*"
  }'
```

**پاسخ:**

```json
{
  "token_type": "Bearer",
  "expires_in": 1296000,
  "access_token": "{ACCESS_TOKEN}",
  "refresh_token": "{REFRESH_TOKEN}"
}
```

| نام | نوع | توضیحات |
|---|---|---|
| `token_type` | string | همیشه `Bearer` |
| `expires_in` | int | طول عمر توکن به ثانیه (۱٬۲۹۶٬۰۰۰ ثانیه ≈ ۱۵ روز) |
| `access_token` | string | توکن JWT برای کار با سرور GraphQL |
| `refresh_token` | string | برای دریافت توکن جدید پس از انقضا |

### مرحله ۴: Refresh Token (تمدید توکن)

پس از انقضای `access_token` (مطابق `expires_in`) از `refresh_token` استفاده کنید.

- **آدرس:** `https://next.zarinpal.com/api/oauth/token`

| نام | نوع | الزامی | پیش‌فرض | توضیحات |
|---|---|---|---|---|
| `grant_type` | string | بله | `refresh_token` | باید `refresh_token` باشد |
| `client_id` | int | بله | — | آی‌دی کلاینت |
| `client_secret` | string | بله | — | کلید کلاینت |
| `refresh_token` | string | بله | — | همان توکن مرحله قبل |
| `scope` | string | بله | `''` | (در مستندات با عنوان @todo آمده است) |

**پاسخ:** مانند مرحله قبل.

### خطاها در احراز هویت

اگر خطایی رخ دهد یا داده نامعتبر باشد، فیلد `errors` حاوی آرایه خطاها و فیلد `data` مقدار `null` خواهد بود.

---

## ۱۸. راهنمای استفاده از API با GraphQL

به جز مراحل احراز هویت، بقیه امکانات API از طریق **GraphQL** در دسترس هستند.

- **آدرس:** `https://next.zarinpal.com/api/v4/graphql`
- **روش:** `POST` با `Content-Type: application/json`
- **احراز هویت:** هدر `Authorization: Bearer {ACCESS_TOKEN}`

```sh
curl 'https://next.zarinpal.com/api/v4/graphql/' \
  -H 'Accept: application/json' \
  -H 'Authorization: Bearer {ACCESS_TOKEN}' \
  --data-binary '{"query":"query { Application { application, platform } }","variables":null}'
```

### نوع عملیات

| نوع | کاربرد |
|---|---|
| `query` | خواندن اطلاعات؛ تغییری ایجاد نمی‌کند |
| `mutation` | تغییر اطلاعات؛ نتیجه تغییر را برمی‌گرداند |

### ساختار پایه

```graphql
query {
  Tickets {
    id
    status
  }
}
```

- فیلدهای مورد نیاز باید مشخص شوند؛ کوئری بدون فیلد معتبر نیست.
- برای نوشتن در یک خط، بین فیلدها به جای خط جدید از **کاما** استفاده کنید:

```graphql
query { Tickets { id, status } }
```

### پاس دادن پارامتر

```graphql
query {
  Tickets(limit: 15) {
    id
    status
  }
}
```

```graphql
query {
  Tickets(limit: 15, offset: 10) {
    id
    status
  }
}
```

- `limit` تعداد حداکثر نتایج را مشخص می‌کند.
- `offset` تعداد نتایج اول را رد می‌کند (مثلاً ۱۰ مورد اول صرف‌نظر شود).

### نمونه Mutation

```graphql
mutation {
  CardAdd(pan: "1111222233334444", expired_at: "2020-02-05 00:00:00") {
    id
  }
}
```

- `CardAdd` از نوع `mutation` است چون داده جدید ذخیره می‌کند.
- نوع بازگشتی `CardAdd` از نوع `Card` است؛ باید فیلدهای موردنیاز را مشخص کنید.

### انواع داده در GraphQL

| نوع | توضیح |
|---|---|
| **Scalar** | داده‌های ساده: `String`، `Int`، `DateTime`، `ID`، `Boolean` |
| **Object** | شیء با چند فیلد؛ هر فیلد یک Key (رشته یکتا) و Value (Scalar، Object یا List) دارد |
| **Enum** | مجموعه مقادیر ثابت |

#### تعریف نوع شیء در شِما

```graphql
type Post {
  id: ID!
  title: String!
  content: String
  comments: [Comment!]
}
```

- علامت **`!`** یعنی مقدار فیلد هرگز `Null` نیست.

#### لیست (List)

```graphql
query {
  Tickets: [Ticket!]!
}
```

- `[Ticket!]!` یعنی: لیست وجود دارد، و هیچ عضوی `Null` نیست.
- `!` بیرون کروشه یعنی لیست **حتماً حداقل یک عضو** دارد؛ اگر نباشد، ممکن است لیست خالی `[]` برگردد.
- لیست‌های اسکالار هم ممکن‌اند: `Numbers: [Int!]` یعنی لیستی از اعداد صحیح.
- داخل هر شیء می‌تواند فیلد لیست‌شده وجود داشته باشد.

### محیط اجرا (Playground)

می‌توانید کوئری‌ها را در محیط GraphiQL تست کنید:
`https://api.zarinpal.com/api/v4/docs/graphiql`

---

## ۱۹. تراکنش‌ها در API

### لیست تراکنش‌های یک ترمینال

ورودی **اجباری**: `terminal_id` (شماره ترمینال درگاه)

| فیلد | توضیح |
|---|---|
| `id` | شناسه پرداخت |
| `status` | وضعیت تراکنش |
| `amount` | مبلغ (ریال) |
| `description` | توضیحات |
| `created_at` | تاریخ و ساعت |

```graphql
query {
  Session (terminal_id: 1915487) {
    id
    status
    amount
    description
    created_at
  }
}
```

**پاسخ نمونه:**

```json
{
  "data": {
    "Session": [
      {
        "id": "388198285",
        "status": "FAILED",
        "amount": 815000,
        "description": "خرید تست",
        "created_at": "2022-11-11T09:36:40+03:30"
      }
    ]
  }
}
```

### فیلتر بر اساس وضعیت (`filter`)

| مقدار فیلتر | معنی |
|---|---|
| `PAID` | موفق، وریفای‌نشده |
| `VERIFIED` | موفق، وریفای‌شده |
| `TRASH` | ناموفق |
| `ACTIVE` | همه تراکنش‌های موفق |

```graphql
query {
  Session (terminal_id: 1915487, filter: PAID) {
    session_tries {
      id
      session_id
      payment_id
      payer_ip
      init_time
      verify_time
      status
      rrn
      card_pan
      created_at
    }
    description
    amount
    fee
  }
}
```

**فیلدهای `session_tries`:** `id`، `session_id`، `payment_id`، `payer_ip`، `init_time` (زمان شروع به ثانیه)، `verify_time`، `status`، `rrn` (شماره ارجاع بانکی)، `card_pan`، `created_at`.

### جستجو در تراکنش‌ها

| پارامتر | توضیح |
|---|---|
| `id` | شناسه پرداخت |
| `reference_id` | شناسه ارجاع |
| `rrn` | شماره ارجاع بانکی |
| `card_pan` | شماره کارت یا بخشی از آن |
| `email` | ایمیل |
| `mobile` | شماره همراه |
| `description` | توضیحات تراکنش |

```graphql
query Sessions($terminal_id: ID, $reference_id: String, $id: ID, $card_pan: String,
$description: String, $mobile: CellNumber, $email: String, $rrn: String) {
  Session(terminal_id: $terminal_id, reference_id: $reference_id, id: $id, card_pan: $card_pan,
  description: $description, mobile: $mobile, email: $email, rrn: $rrn) {
    id
    status
    amount
    description
    created_at
  }
}
```

**Query Variables نمونه:**

```json
{
  "card_pan": "8920",
  "rrn": "141186863321",
  "reference_id": "38540123901",
  "terminal_id": "337759",
  "id": "385401239",
  "mobile": "09121234567"
}
```

**پاسخ نمونه:**

```json
{
  "data": {
    "Session": [
      {
        "id": "385401239",
        "status": "PAID",
        "amount": 11000,
        "description": "پرداخت کننده: Test",
        "created_at": "2022-10-28T13:19:05+03:30"
      }
    ]
  }
}
```

---

## ۲۰. حساب بانکی در API

### لیست حساب‌های بانکی

```graphql
query getBankAccounts {
  resource: BankAccounts {
    id
    iban
    status
    is_legal
    holder_name
    type
    issuing_bank {
      name
      slug
    }
  }
}
```

**پاسخ نمونه:**

```json
{
  "data": {
    "resource": [
      {
        "id": "402811",
        "iban": "IR123456789123456478945165",
        "status": "ACTIVE",
        "is_legal": false,
        "holder_name": "علی علیپور",
        "type": "PERSONAL",
        "issuing_bank": {
          "name": "بانک مهر ایران",
          "slug": "Mehr"
        }
      }
    ]
  }
}
```

### افزودن حساب بانکی

- اگر حساب به **خودتان** تعلق دارد، `type` باید `PERSONAL` باشد.
- اگر حساب **شریک تجاری** شماست، `type` باید `SHARE` باشد.

```graphql
mutation BankAccountAdd(
  $iban: String!,
  $is_legal: Boolean!,
  $type: BankAccountTypeEnum
) {
  BankAccountAdd(
    iban: $iban,
    is_legal: $is_legal,
    type: $type
  ) {
    id
    iban
    name
    status
    type
    is_legal
    holder_name
    issuing_bank { name slug }
    expired_at
    deleted_at
  }
}
```

**Query Variables:**

```json
{ "iban": "IR123456789123456478945165", "is_legal": false, "type": "SHARE" }
```

**پاسخ نمونه:**

```json
{
  "data": {
    "BankAccountAdd": {
      "id": "454781",
      "iban": "IR123456789123456478945165",
      "name": null,
      "status": "PENDING",
      "type": "SHARE",
      "is_legal": false,
      "holder_name": null,
      "issuing_bank": {
        "name": "بانک پاسارگاد",
        "slug": "Pasargad"
      },
      "expired_at": null,
      "deleted_at": null
    }
  }
}
```

> پس از افزودن، وضعیت حساب `PENDING` است تا تأیید شود.

---

## ۲۱. درگاه‌ها (Terminal) در API

### لیست درگاه‌ها

| فیلد | توضیح |
|---|---|
| `id` | شماره ترمینال درگاه |
| `status` | وضعیت درگاه |
| `preferred_bank_account_id` | شماره حساب بانکی تنظیم‌شده برای تسویه |
| `domain` | دامنه درگاه |
| `support_phone` | شماره پشتیبانی |
| `key` | مرچنت‌کد درگاه |
| `name` | نام درگاه |
| `logo` | لوگو |
| `created_at` | تاریخ ایجاد |
| `updated_at` | تاریخ آخرین بروزرسانی |

```graphql
query {
  Terminals {
    id
    status
    preferred_bank_account_id
    domain
    support_phone
    key
    name
    logo
    created_at
    updated_at
  }
}
```

**پاسخ نمونه:**

```json
{
  "data": {
    "Terminals": [
      {
        "id": "1915487",
        "status": "ACTIVE",
        "preferred_bank_account_id": "353",
        "domain": "example.com",
        "support_phone": "09123456798",
        "key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "name": "علی علیپور",
        "logo": "https://test.example.com/1561651asdd5f1a2sd1",
        "created_at": "2022-07-17T15:26:43+04:30",
        "updated_at": "2022-12-12T11:24:12+03:30"
      }
    ]
  }
}
```

### درخواست ثبت درگاه جدید

| ورودی | توضیح |
|---|---|
| `mcc_id` | شناسه دسته‌بندی (کسب‌وکار) |
| `bank_account_id` | شناسه حساب بانکی |
| `domain` | آدرس دامنه |
| `support_phone` | شماره تلفن پشتیبانی |
| `name` | نام درگاه |

```graphql
mutation TerminalAdd(
  $mcc_id: ID!,
  $domain: String!,
  $support_phone: CellNumber!,
  $name: String!,
  $bank_account_id: ID!
) {
  TerminalAdd(
    mcc_id: $mcc_id,
    domain: $domain,
    support_phone: $support_phone,
    name: $name,
    bank_account_id: $bank_account_id
  ) {
    id
    mcc_id
    preferred_bank_account_id
    domain
    support_phone
    key
    name
    status
    logo
    created_at
    updated_at
    deleted_at
  }
}
```

**Query Variables:**

```json
{"mcc_id": "186", "bank_account_id": "545", "domain": "test.ir", "support_phone": "09123456789", "name": "درگاه من"}
```

**پاسخ نمونه:**

```json
{
  "data": {
    "TerminalAdd": {
      "id": "1789487",
      "mcc_id": "186",
      "preferred_bank_account_id": "454",
      "domain": "test.ir",
      "support_phone": "09123456789",
      "key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "name": "درگاه من",
      "status": "PENDING",
      "logo": "https://test.example.com/1a5615asd66233g33j",
      "created_at": "2020-08-31T02:00:30+04:30",
      "updated_at": "2020-08-31T02:00:30+04:30",
      "deleted_at": null
    }
  }
}
```

> پس از ثبت، وضعیت درگاه `PENDING` است.

---

## ۲۲. نمونه کد Python

### ۲۲.۱ نصب

**پیش‌نیازها:**

1. Python نسخه **۳.۱۲** یا بالاتر
2. ابزار **pip** (معمولاً همراه Python نصب می‌شود)

```bash
pip install zarinpal-py-sdk
```

یا:

```bash
pip3 install zarinpal-py-sdk
```

### ۲۲.۲ پیکربندی

برای هر درخواست باید `merchantId` و حالت `sandbox` تنظیم شود. برای متدهای مدیریت تراکنش (مانند لیست تراکنش‌ها) به `accessToken` نیز نیاز است.

```python
from zarinpal import ZarinPal
from utils.Config import Config

config = Config(
    merchant_id="Your merchant code",
    access_token="your-access-token",
    sandbox=True,
)
zarinpal = ZarinPal(config)
```

**تنظیم ثابت در فایل Config** (برای جلوگیری از تکرار):

```python
class Config:
    def __init__(self):
        self.sandbox = sandbox  # True یا False
        self.merchant_id = merchant_id
        self.access_token = access_token
```

**راهنما:**

- `merchant_id` را از **بخش تنظیمات درگاه** دریافت کنید.
- `access_token` را از بخش **نشست‌های فعال** پنل دریافت کنید.

### ۲۲.۳ متد request (درخواست پرداخت)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `amount` | Integer | بله | مبلغ به ریال؛ **حداقل ۱۰٬۰۰۰ ریال** |
| `description` | String | بله | توضیحات تراکنش (شماره سفارش یا نام محصول) |
| `callback_url` | String | بله | آدرس بازگشت |
| `mobile` | String | خیر | شماره موبایل کاربر |
| `email` | String | خیر | ایمیل کاربر |
| `referrer_id` | String | خیر | کد معرف |
| `currency` | String | خیر | `IRR` (پیش‌فرض) یا `IRT` |
| `cardPan` | String | خیر | شماره کارت موردنظر |

**نمونه کد کامل:**

```python
from zarinpal import ZarinPal
from utils.Config import Config


def initiate_payment():
    try:
        config = Config(
            merchant_id="your merchant code",
            sandbox=True,
        )
        zarinpal = ZarinPal(config)
        response = zarinpal.payments.create(
            {
                "amount": 20000,
                "callback_url": "https://zarinpal.com/",
                "description": "Payment creat",
                "mobile": "09123456789",
                "email": "customer@example.com",
                "cardPan": ["6219861034529007", "5022291073776543"],
                "referrer_id": "affiliate123",
            }
        )
        print("Payment created successfully:", response)

        if "data" in response and "authority" in response["data"]:
            authority = response["data"]["authority"]
            payment_url = zarinpal.payments.generate_payment_url(authority)
            print("Payment URL:", payment_url)
        else:
            print("Authority not found in response.")
    except Exception as e:
        print("Error during payment creation:", e)


if __name__ == "__main__":
    initiate_payment()
```

### ۲۲.۴ متد verify (تأیید پرداخت)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `authority` | String | بله | از کوئری‌استرینگ بازگشت به `callback_url` |
| `amount` | Integer | بله | باید از دیتابیس خوانده شود و با مبلغ اصلی تطابق داشته باشد |

**نمونه کد کامل:**

```python
from zarinpal import ZarinPal
from utils.Config import Config

authority = "Your Authority"
status = "OK"


def get_amount_from_database(authority):
    return 20000


def verify_payment(authority, status):
    if status == "OK":
        amount = get_amount_from_database(authority)
        if amount:
            try:
                config = Config(
                    merchant_id="Your merchant code",
                    sandbox=True,
                )
                zarinpal = ZarinPal(config)
                response = zarinpal.verifications.verify(
                    {
                        "amount": amount,
                        "authority": authority,
                    }
                )
                if response["data"]["code"] == 100:
                    print("Payment Verified:")
                    print("Reference ID:", response["data"]["ref_id"])
                    print("Card PAN:", response["data"]["card_pan"])
                    print("Fee:", response["data"]["fee"])
                elif response["data"]["code"] == 101:
                    print("Payment already verified.")
                else:
                    print("Transaction failed with code:", response["data"]["code"])
            except Exception as e:
                print("Payment Verification Failed:", e)
        else:
            print("No Matching Transaction Found For This Authority Code.")
    else:
        print("Transaction was cancelled or failed.")


if __name__ == "__main__":
    verify_payment(authority, status)
```

> **نکته:** اگر `status` برابر `OK` نباشد، verify فراخوانی نمی‌شود.

### ۲۲.۵ متد inquiry (استعلام تراکنش)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | مرچنت‌کد |
| `authority` | String | بله | کد یکتای درخواست پرداخت |

**خروجی:**

| پارامتر | نوع | توضیحات |
|---|---|---|
| `code` | Integer | ۱۰۰ یعنی موفق |
| `message` | String | پیام وضعیت |
| `status` | String | وضعیت نهایی (موفق یا لغوشده) |

```python
from zarinpal import ZarinPal
from utils.Config import Config


def inquire_transaction():
    try:
        config = Config(
            merchant_id="Your merchant code",
            sandbox=True,
        )
        zarinpal = ZarinPal(config)
        response = zarinpal.inquiries.inquire(
            {
                # Enter authority:
                "authority": " "
            }
        )
        print("Inquiry Result:", response)
    except Exception as e:
        print("Error during inquiry:", e)
        if hasattr(e, "response"):
            print("Error Details:", e)
        else:
            print("No additional error details available.")


if __name__ == "__main__":
    inquire_transaction()
```

### ۲۲.۶ متد unVerified (استعلام تراکنش‌های تأیید نشده)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |

**خروجی:** `code` (عدد وضعیت) و `authorities` (آرایه JSON‌شده شامل نوع درگاه و زمان پرداخت).

```python
from zarinpal import ZarinPal
from utils.Config import Config


def get_unverified_payments():
    try:
        config = Config(
            merchant_id="Your merchant code",
            sandbox=True,
        )
        zarinpal = ZarinPal(config)
        unverified_payments = zarinpal.unverified.list()
        print("Unverified Payments:", unverified_payments)
    except Exception as e:
        print("Error fetching unverified payments:", e)


if __name__ == "__main__":
    get_unverified_payments()
```

### ۲۲.۷ متد reverse (ریورس)

- امکان ریورس فقط در **۳۰ دقیقه اول** پس از پرداخت وجود دارد.
- IP سرور باید برای درگاه تنظیم باشد، وگرنه خطای **-62** دریافت می‌شود.

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `merchant_id` | String | بله | کد ۳۶ کاراکتری پذیرنده |
| `authority` | String | بله | آتوریتی تراکنش برای ریورس |

```python
from zarinpal import ZarinPal
from utils.Config import Config


def reverse_transaction():
    try:
        config = Config(
            merchant_id="Your Merchent Id",
            sandbox=True,
        )
        zarinpal = ZarinPal(config)
        response = zarinpal.reversals.reverse(
            {
                # Enter authority:
                "authority": " ",
            }
        )
        print("Transaction Reversed Successfully:", response)
    except Exception as e:
        print("Error during transaction reversal:", e)


if __name__ == "__main__":
    reverse_transaction()
```

### ۲۲.۸ متد transaction (لیست تراکنش‌ها)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `terminal_id` | String | بله | شناسه ترمینال |
| `filter` | String | خیر | `PAID`، `VERIFIED`، `TRASH` یا `ACTIVE` |
| `offset` | Integer | خیر | شروع ردیف‌ها |
| `limit` | Integer | خیر | تعداد ردیف‌ها |

**خروجی:** `id`، `status` (مثلاً `PAID` یا `FAILED`)، `amount` (ریال)، `description`، `created_at`.

```python
from zarinpal import ZarinPal
from utils.Config import Config


def get_transactions():
    try:
        config = Config(
            access_token="Your Token",
        )
        zarinpal = ZarinPal(config)
        transactions = zarinpal.transactions.list(
            {
                "terminal_id": "Your terminal ID",
                "filter": "PAID",
                "limit": 10,
                "offset": 0,
            }
        )
        print("Transactions List:", transactions)
    except Exception as e:
        print("Error fetching transactions:", e)


if __name__ == "__main__":
    get_transactions()
```

### ۲۲.۹ متد fee_calculation (محاسبه کارمزد)

| پارامتر | نوع | الزامی | توضیحات |
|---|---|---|---|
| `merchant_id` | str | بله | کد پذیرنده |
| `amount` | int | بله | ریال، بیشتر از ۱۰۰۰ |
| `currency` | str | خیر | `IRR` (پیش‌فرض) یا `IRT` |

**خروجی:** `code` (۱۰۰ = موفق)، `message`، `amount`، `fee`، `fee_type` (`Merchant` یا `Payer`)، `suggested_amount`.

```python
from zarinpal import ZarinPal
from utils.Config import Config


def calculate_fee():
    try:
        config = Config(
            merchant_id="",
        )
        zarinpal = ZarinPal(config)
        fee = zarinpal.fee.calculate({"amount": 90000, "currency": "IRR"})
        print("Fee Calculation Result:", fee)
    except Exception as e:
        print("Error calculating fee:", e)


if __name__ == "__main__":
    calculate_fee()
```

### ۲۲.۱۰ جدول خلاصه متدهای SDK

| متد | کاربرد | نیازمند |
|---|---|---|
| `payments.create` | ایجاد درخواست پرداخت | merchant_id |
| `payments.generate_payment_url` | ساخت URL صفحه پرداخت از authority | — |
| `verifications.verify` | تأیید پرداخت | merchant_id |
| `inquiries.inquire` | استعلام وضعیت | merchant_id |
| `unverified.list` | لیست تراکنش‌های تأیید نشده | merchant_id |
| `reversals.reverse` | ریورس تراکنش | merchant_id + IP تنظیم‌شده |
| `transactions.list` | لیست تراکنش‌ها | access_token |
| `fee.calculate` | محاسبه کارمزد | merchant_id |

---

## ۲۳. سرویس MCP زرین‌پال

**MCP (Model Context Protocol)** یک استاندارد باز برای اتصال ابزارهای هوش مصنوعی به منابع داده است. با این سرویس، دستیارهایی مانند **Claude Code**، **Cursor** و **Claude Desktop** می‌توانند مستندات رسمی زرین‌پال را به‌صورت زنده جست‌وجو و مطالعه کنند.

### چرا این سرویس؟

- دستیار به‌جای حدس زدن پارامترها و آدرس‌ها، از مستندات رسمی و به‌روز استفاده می‌کند.
- نسخه مستندات همیشه با آخرین نسخه منتشرشده سایت هم‌خوان است.
- مستندات شامل درگاه، API، نمونه کدها، افزونه‌ها و لیست کامل خطاهاست.
- **بدون نیاز به کلید API یا احراز هویت** و به‌صورت عمومی در دسترس است.

**آدرس سرویس:**

```txt
https://www.zarinpal.com/docs/mcp
```

### ابزارهای سرویس

| ابزار | کاربرد |
|---|---|
| `search_docs` | جست‌وجوی متنی در تمام مستندات (فارسی یا انگلیسی) |
| `get_doc` | دریافت متن کامل یک صفحه |
| `list_docs` | فهرست صفحات به تفکیک بخش |
| `get_error_code` | توضیح کدهای خطا و وضعیت وب‌سرویس (مثل -9 یا -31) |

### نمونه پرسش‌ها

- «چطور درخواست پرداخت با زرین‌پال در PHP بزنم؟»
- «خطای -51 یعنی چه؟»
- «تفاوت واحد پولی IRR و IRT در درگاه چیست؟»

### راه‌اندازی

**Claude Code** (در ترمینال):

```sh
claude mcp add --transport http zarinpal-docs https://www.zarinpal.com/docs/mcp
```

بررسی اتصال:

```sh
claude mcp list
```

**Cursor** (`Settings → MCP → Add Server` یا ویرایش `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "zarinpal-docs": {
      "url": "https://www.zarinpal.com/docs/mcp"
    }
  }
}
```

**Claude Desktop** (`Settings → Developer → Edit Config` و افزودن به `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zarinpal-docs": {
      "type": "http",
      "url": "https://www.zarinpal.com/docs/mcp"
    }
  }
}
```

پس از ذخیره، برنامه را یک‌بار ببندید و دوباره باز کنید؛ سرویس `zarinpal-docs` باید در آیکون ابزارها (Tools) دیده شود.

**سایر ابزارهای سازگار:** هر ابزاری که از **Streamable HTTP** پشتیبانی کند، با همان آدرس و نوع `http` کار می‌کند.

> سرویس **stateless** است و نیازی به Session یا اتصال پایدار ندارد.

### رفع اشکال

| مشکل | راه‌حل |
|---|---|
| سرویس در فهرست ابزارها دیده نمی‌شود | آدرس `https://www.zarinpal.com/docs/mcp/health` را باز کنید؛ باید JSON با `"status": "ok"` برگرداند. |
| پاسخ‌ها قدیمی به نظر می‌رسند | مقادیر `gitSha` و `builtAt` در صفحه health نسخه مستندات را نشان می‌دهند. |
| خطای اتصال در شبکه سازمانی | مطمئن شوید دامنه `www.zarinpal.com` فیلتر نیست. |

---

## ۲۴. جمع‌بندی مراحل پیاده‌سازی

1. **دریافت اطلاعات:** `merchant_id` را از تنظیمات درگاه و در صورت نیاز `client_id`/`client_secret` را از پشتیبانی بگیرید.
2. **تنظیم IP سرور:** IP سرور اصلی را از بخش افزونه‌ها (نمونه کدها) دریافت و در پنل ثبت کنید. (برای ریورس الزامی است.)
3. **تست در Sandbox:** آدرس‌ها را به `sandbox.zarinpal.com` تغییر دهید و `merchant_id` تستی UUID بگذارید.
4. **ایجاد درخواست پرداخت:** مبلغ، توضیحات، `callback_url` و در صورت نیاز موبایل/ایمیل/سبد خرید را ارسال کنید.
5. **بررسی کد و انتقال خریدار:** اگر `code=100` و `authority` دریافت شد، خریدار را به صفحه پرداخت هدایت کنید.
6. **دریافت بازگشت:** `Status` را بررسی کنید. فقط با `OK` ادامه دهید.
7. **Verify:** مبلغ را از دیتابیس خوانده و با `authority` و `amount` verify کنید. کد ۱۰۰ موفق و ۱۰۱ یعنی قبلاً انجام شده.
8. **نمایش نتیجه:** `ref_id` را به کاربر نشان دهید؛ در خطا، پیام متناسب با کد را نمایش دهید.
9. **مدیریت مغایرت:** از `unVerified` برای پیدا کردن پرداخت‌های تأیید نشده و از `inquiry` برای بررسی وضعیت استفاده کنید.
10. **ریورس (در صورت نیاز):** فقط در ۳۰ دقیقه اول و با IP تنظیم‌شده.
11. **تراکنش‌ها و گزارش‌ها:** با GraphQL و `Session` یا متد `transactions.list` تراکنش‌ها را بررسی کنید.
12. **همکاری در فروش (اختیاری):** `referrer_id` را ارسال کنید.

---

## ۲۵. نکات و ناهماهنگی‌های مستندات

این موارد از متن مستندات استخراج شده‌اند تا در پیاده‌سازی به آن‌ها توجه شود:

1. **واحد مبلغ:** در بیشتر متدها مبلغ به **ریال** است، اما نمونه‌های اعتبارسنجی و همکاری در فروش با `currency: "IRT"` آمده‌اند. هنگام استفاده از تومان حتماً واحد را مشخص کنید و از یکسان بودن مبلغ در request و verify مطمئن شوید.
2. **حداقل مبلغ:** در SDK پایتون حداقل پرداخت **۱۰٬۰۰۰ ریال** و در FeeCalculation حداقل **۱۰۰۰ ریال** ذکر شده است.
3. **حداکثر مبلغ:** طبق کد -41، حداکثر **۱۰۰ میلیون تومان** است.
4. **حداکثر توضیحات:** `description` باید حداکثر **۵۰۰ کاراکتر** باشد (کد -9).
5. **JSON نامعتبر در نمونه:** نمونه `card_pan` کاما انتهایی دارد که JSON معتبر نیست.
6. **نمونه `amount` در Verify:** در بعضی نمونه‌ها مبلغ به صورت رشته (`"1000"`) و در بعضی عدد (`1000`) آمده است؛ مطابق نوع Integer مستندات، عدد ارسال شود.
7. **کد -31:** در بخش MCP ذکر شده ولی در جدول خطاهای اصلی نیست.
8. **فیلدهای @todo:** در مستندات احراز هویت، توضیح فیلدهای `otp_time_diff` و `scope` هنوز کامل نشده است.
9. **تایپ `cardPan` در SDK:** در SDK به صورت آرایه (چند کارت) ارسال شده، اما در API مستقیم به صورت `card_pan` در `metadata` است.
10. **تعداد ۳۰ دقیقه:** مهلت ریورس ۳۰ دقیقه است؛ پس از آن، ریورس با کد -63 رد می‌شود.
11. **unVerified:** فقط ۱۰۰ تراکنش آخر را برمی‌گرداند.
12. **Authority:** در سندباکس با **S** و در محیط واقعی با **A** شروع می‌شود.
13. **کد 101:** خطا نیست؛ به معنای موفق بودن و Verify قبلی است.
14. **مهلت وریفای:** اگر Verify انجام نشود، مبلغ به خریدار برمی‌گردد؛ به‌ویژه در حالت غیرخودکار دقت کنید.
