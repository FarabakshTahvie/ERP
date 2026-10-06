# سرویس API پوش نوتیفیکیشن نجوا

**نسخه ۱.۰.۰**

## فهرست مطالب

1. [ارسال پوش نوتیفیکیشن به توکن خاص](#۱-ارسال-پوش-نوتیفیکیشن-به-توکن-خاص)
2. [ارسال پوش نوتیفیکیشن به همه توکن‌ها (broadcast)](#۲-ارسال-پوش-نوتیفیکیشن-به-همه-توکنها-broadcast)
3. [ارسال پوش نوتیفیکیشن‌های شخصی‌سازی‌شده به توکن‌های خاص](#۳-ارسال-پوش-نوتیفیکیشنهای-شخصیسازیشده-به-توکنهای-خاص)
4. [لغو پوش نوتیفیکیشن زمان‌بندی‌شده به توکن خاص](#۴-لغو-پوش-نوتیفیکیشن-زمانبندیشده-به-توکن-خاص)
5. [لغو پوش نوتیفیکیشن زمان‌بندی‌شده به همه توکن‌ها (broadcast)](#۵-لغو-پوش-نوتیفیکیشن-زمانبندیشده-به-همه-توکنها-broadcast)
6. [دریافت گزارش ارسال به توکن خاص](#۶-دریافت-گزارش-ارسال-به-توکن-خاص)
7. [دریافت گزارش ارسال به همه توکن‌ها (broadcast)](#۷-دریافت-گزارش-ارسال-به-همه-توکنها-broadcast)
8. [دریافت پروفایل توکن‌ها](#۸-دریافت-پروفایل-توکنها)
9. [دریافت وب‌سایت‌های کاربر](#۹-دریافت-وبسایتهای-کاربر)

> **توضیح:** در متن اصلی PDF، سند در فهرست از «دریافت تعداد توکن‌های ایجادشده و حذف‌شده» (صفحه ۲۲) نیز نام برده بود، اما محتوای آن در بدنهٔ سند وجود نداشت؛ به همین دلیل در این نسخه نیامده است.

---

## موارد مشترک بین همه متدها

| مورد | توضیح |
|---|---|
| **احراز هویت** | یک `apiKey` معتبر باید در header درخواست قرار داده شود. |
| **وایت‌لیست IP** | برای ارسال پوش تراکنشی (با استفاده از API) و دریافت گزارش‌ها، وایت‌لیست کردن IP الزامی است. |
| **فرمت لینک‌ها** | تمامی لینک‌های مقصد باید با فرمت `https://{URL_WEBSITE_DESTINATION}` ارسال شوند. |
| **Content-Type** | `multipart/form-data` |

### محدودیت‌های محتوا (متدهای ارسال)

| مورد | سقف مجاز |
|---|---|
| طول عنوان | ۲۵۰ کاراکتر |
| طول متن | ۴۰۰ کاراکتر |
| طول لینک اصلی | ۲۵۰ کاراکتر |
| طول عنوان دکمه‌ها | ۲۰ کاراکتر |
| طول لینک دکمه‌ها | ۸۰ کاراکتر |
| حجم فایل آیکون | ۱۰۰ کیلوبایت |
| حجم تصویر نوتیفیکیشن | ۲ مگابایت |
| تعداد توکن در هر درخواست | ۱۰۰۰ توکن |

> فایل آیکون و تصویر باید **آپلود** شوند؛ نحوهٔ انجام این کار بسته به زبان برنامه‌نویسی و ابزار مورد استفاده متفاوت است.

---

## ۱. ارسال پوش نوتیفیکیشن به توکن خاص

کاربرد این متد ارسال پوش نوتیفیکیشن به توکن خاص مورد نظر مشتری است. در این متد امکان ارسال به چندین توکن وجود دارد؛ برای این کار تنها لازم است تمامی توکن‌های مورد نظر در پارامتر `tokens` قرار داده شوند.

**ساختار URL (متد `POST`):**

```
https://push.najva.com/v1/send/token/
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که از آن نوتیفیکیشن‌ها ارسال شوند. |
| `ttl` | اجباری | Integer | مدت زمان معتبر بودن نوتیفیکیشن (به ساعت). |
| `date` | اختیاری | String | تاریخ و زمان برنامه‌ریزی‌شده برای ارسال، به فرمت RFC3339. |
| `tokens[]` | اجباری | String | به تعداد توکن‌های مورد نظر، از این پارامتر به درخواست افزوده می‌شود. |
| `message.title` | اجباری | String | عنوان نوتیفیکیشن. |
| `message.body` | اجباری | String | متن نوتیفیکیشن. |
| `message.icon` | اختیاری | Image | آیکون نوتیفیکیشن. |
| `message.image` | اختیاری | Image | تصویر نوتیفیکیشن. |
| `message.notification_click.click_url` | اجباری | String | لینک مقصد در صورت کلیک روی نوتیفیکیشن. |
| `message.button_1.title` | اختیاری | String | عنوان دکمهٔ اول. |
| `message.button_1.click_url` | اختیاری | String | لینک مقصد در صورت کلیک روی دکمهٔ اول. |
| `message.button_2.title` | اختیاری | String | عنوان دکمهٔ دوم. |
| `message.button_2.click_url` | اختیاری | String | لینک مقصد در صورت کلیک روی دکمهٔ دوم. |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `request_id` | UUID | شناسه یکتای درخواست. |
| `tokens` | Array | لیست وضعیت ارسال به توکن‌های داده‌شده. |
| `tokens[n].token` | UUID | توکن مورد ارسال. |
| `tokens[n].status` | String | وضعیت ارسال به توکن مذکور. |
| `tokens[n].cost` | Integer | هزینهٔ ارسال پیام به توکن مذکور. هزینه پس از رسیدن پیام به مخاطب از حساب شما کسر خواهد شد. |

### نکات

- در هر درخواست مجاز به ارسال تا سقف **۱۰۰۰ توکن** هستید.
- وضعیت ارسال (`status`) یکی از سه مقدار زیر است:
  - `Sent`: ارسال موفق به توکن داده‌شده.
  - `Scheduled`: توکن معتبر است و فیلد `date` برای زمان‌بندی ارسال در آینده ارائه شده است.
  - `InvalidToken`: توکن نامعتبر است یا کاربر غیرفعال است.
- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- لینک‌های مقصد باید با `https://` شروع شوند.
- برای ارسال پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `415` | حجم غیرمجاز فایل‌های ورودی. |
| `416` | آدرس IP مبدأ مطابقت ندارد. |
| `414` | تعداد توکن‌های ارسال‌شده بیشتر از ۱۰۰۰ عدد است. |
| `418` | اعتبار شما برای ارسال کافی نیست. |

### نمونه درخواست

```bash
curl --location 'https://push.najva.com/v1/send/token/' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'ttl="24"' \
--form 'date="2025-07-21T21:04:45+03:30"' \
--form 'tokens[]="21a4548a-574d-4425-9af2-6a0e70dae649"' \
--form 'tokens[]="9615c2ea-9d2d-4343-b880-4e79cb115384"' \
--form 'message.title="transactional sample"' \
--form 'message.body="this is the body of transactional sample"' \
--form 'message.icon=@/path/to/your/icon.jpg' \
--form 'message.image=@/path/to/your/image.jpg' \
--form 'message.notification_click.click_url="https://google.com"' \
--form 'message.button_1.title="Button One"' \
--form 'message.button_1.click_url="https://najva.com"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
    "tokens": [
      {
        "token": "21a4548a-574d-4425-9af2-6a0e70dae649",
        "status": "InvalidToken",
        "cost": 0
      },
      {
        "token": "9615c2ea-9d2d-4343-b880-4e79cb115384",
        "status": "Scheduled",
        "cost": 25
      }
    ]
  }
}
```

---

## ۲. ارسال پوش نوتیفیکیشن به همه توکن‌ها (broadcast)

کاربرد این متد ارسال پوش نوتیفیکیشن به همهٔ توکن‌های مشتری است.

**ساختار URL (متد `POST`):**

```
https://push.najva.com/v1/send/bulk/
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که از آن نوتیفیکیشن‌ها ارسال شوند. |
| `ttl` | اجباری | Integer | مدت زمان معتبر بودن نوتیفیکیشن (به ساعت). |
| `utm_has` | اختیاری | Bool | اضافه کردن UTM به لینک‌ها. |
| `date` | اختیاری | String | تاریخ و زمان برنامه‌ریزی‌شده برای ارسال، به فرمت RFC3339. |
| `message.title` | اجباری | String | عنوان نوتیفیکیشن. |
| `message.body` | اجباری | String | متن نوتیفیکیشن. |
| `message.icon` | اختیاری | Image | آیکون نوتیفیکیشن. |
| `message.image` | اختیاری | Image | تصویر نوتیفیکیشن. |
| `message.notification_click.click_url` | اجباری | String | لینک مقصد در صورت کلیک روی نوتیفیکیشن. |
| `message.button_1.title` | اختیاری | String | عنوان دکمهٔ اول. |
| `message.button_1.click_url` | اختیاری | String | لینک مقصد دکمهٔ اول. |
| `message.button_2.title` | اختیاری | String | عنوان دکمهٔ دوم. |
| `message.button_2.click_url` | اختیاری | String | لینک مقصد دکمهٔ دوم. |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `campaign_id` | Integer | شناسه یکتای کمپین ساخته‌شده. |
| `execution_id` | Integer | شناسه یکتای فرآیند ارسال کمپین. |
| `execution_status` | String | وضعیت فرآیند ارسال کمپین. |

### نکات

- وضعیت فرآیند ارسال کمپین در پاسخ به ایجاد کمپین `Scheduled` است. در گزارش‌های بعدی یکی از مقادیر `Completed`، `Running`، `Scheduled` یا `Canceled` را خواهد داشت.
- محدودیت‌های طول و حجم، احراز هویت، فرمت لینک و وایت‌لیست IP مطابق [موارد مشترک](#موارد-مشترک-بین-همه-متدها) است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `415` | حجم غیرمجاز فایل‌های ورودی. |
| `416` | آدرس IP مبدأ مطابقت ندارد. |

### نمونه درخواست

```bash
curl --location 'https://push.najva.com/v1/send/bulk/' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'ttl="24"' \
--form 'date="2025-07-21T21:04:45+03:30"' \
--form 'message.title="transactional sample"' \
--form 'message.body="this is the body of transactional sample"' \
--form 'message.icon=@/path/to/your/icon.jpg' \
--form 'message.image=@/path/to/your/image.jpg' \
--form 'message.notification_click.click_url="https://google.com"' \
--form 'message.button_1.title="Button One"' \
--form 'message.button_1.click_url="https://najva.com"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "campaign_id": 17834,
    "execution_id": 19937,
    "execution_status": "Scheduled"
  }
}
```

---

## ۳. ارسال پوش نوتیفیکیشن‌های شخصی‌سازی‌شده به توکن‌های خاص

کاربرد این متد ارسال پوش نوتیفیکیشن شخصی‌سازی‌شده به توکن‌های خاص است. در این متد می‌توان پیام‌های متفاوتی به چندین توکن ارسال کرد؛ برای این کار باید لیست پیام‌ها به همراه توکن مربوطه در قالب زیر قرار داده شوند.

**ساختار URL (متد `POST`):**

```
https://push.najva.com/v1/send/peer/
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که از آن نوتیفیکیشن‌ها ارسال شوند. |
| `ttl` | اجباری | Integer | مدت زمان معتبر بودن نوتیفیکیشن (به ساعت). |
| `date` | اختیاری | String | تاریخ و زمان برنامه‌ریزی‌شده برای ارسال، به فرمت RFC3339. |
| `messages.token[]` | اجباری | String | توکن دریافت‌کنندهٔ n‌امین پیام. |
| `messages.title[]` | اجباری | String | عنوان n‌امین نوتیفیکیشن. |
| `messages.body[]` | اجباری | String | متن n‌امین نوتیفیکیشن. |
| `message.icon` | اختیاری | Image | آیکون **همهٔ** نوتیفیکیشن‌ها. |
| `message.image` | اختیاری | Image | تصویر **همهٔ** نوتیفیکیشن‌ها. |
| `notification_click.click_url` | اجباری | String | لینک مقصد در صورت کلیک روی نوتیفیکیشن. |
| `button_1.title` | اختیاری | String | عنوان دکمهٔ اول. |
| `button_1.click_url` | اختیاری | String | لینک مقصد دکمهٔ اول. |
| `button_2.title` | اختیاری | String | عنوان دکمهٔ دوم. |
| `button_2.click_url` | اختیاری | String | لینک مقصد دکمهٔ دوم. |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `request_id` | UUID | شناسه یکتای درخواست. |
| `tokens` | Array | لیست وضعیت ارسال به توکن‌های داده‌شده. |
| `tokens[n].token` | UUID | توکن مورد ارسال. |
| `tokens[n].status` | String | وضعیت ارسال به توکن مذکور. |
| `tokens[n].cost` | Integer | هزینهٔ ارسال پیام به توکن مذکور (پس از رسیدن پیام به مخاطب از حساب کسر می‌شود). |

### نکات

- آیکون، تصویر و لینک‌های همهٔ نوتیفیکیشن‌ها **یکسان** است و فقط **عنوان و بدنه** شخصی‌سازی می‌شود.
- در هر درخواست مجاز به ارسال تا سقف **۱۰۰۰ توکن** هستید.
- وضعیت ارسال (`status`): `Sent`، `Scheduled` یا `InvalidToken` (مانند متد ارسال به توکن خاص).
- سایر محدودیت‌ها مطابق [موارد مشترک](#موارد-مشترک-بین-همه-متدها) است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `415` | حجم غیرمجاز فایل‌های ورودی. |
| `416` | آدرس IP مبدأ مطابقت ندارد. |
| `418` | اعتبار شما کافی نیست. |

### نمونه درخواست

```bash
curl --location 'https://push.najva.com/v1/send/peer/' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Your_Api_Key}' \
--form 'website_id="45100"' \
--form 'ttl="24"' \
\
--form 'messages.token[]="21a4548a-574d-4425-9af2-6a0e70dae649"' \
--form 'messages.title[]="Special Offer For Reza!"' \
--form 'messages.body[]="Hi Reza, don'\''t miss out on our 20% off flash sale today."' \
\
--form 'messages.token[]="9615c2ea-9d2d-4343-b880-4e79cb115384"' \
--form 'messages.title[]="Special Offer For Sara!"' \
--form 'messages.body[]="Hi Sara, don'\''t miss out on our 20% off flash sale today."' \
\
--form 'message.icon=@/path/to/your/icon.jpg' \
--form 'message.image=@/path/to/your/image.jpg' \
--form 'notification_click.click_url="https://example.com/flash-sale/"' \
--form 'button_1.title="Shop Now"' \
--form 'button_1.click_url="https://example.com/flash-sale/shop"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
    "tokens": [
      {
        "token": "21a4548a-574d-4425-9af2-6a0e70dae649",
        "status": "InvalidToken",
        "cost": 0
      },
      {
        "token": "9615c2ea-9d2d-4343-b880-4e79cb115384",
        "status": "Sent",
        "cost": 25
      }
    ]
  }
}
```

---

## ۴. لغو پوش نوتیفیکیشن زمان‌بندی‌شده به توکن خاص

کاربرد این متد لغو ارسال پوش نوتیفیکیشن از پیش زمان‌بندی‌شده به توکن‌های خاص است. 

> ⚠️ ورودی این متد **لیست توکن‌ها نیست**، بلکه لیست **شناسهٔ درخواست‌ها** (`request_id`) است که از متد ارسال دریافت می‌کنید. می‌توانید چندین درخواست زمان‌بندی‌شده را هم‌زمان لغو کنید.

**ساختار URL (متد `POST`):**

```
https://push.najva.com/v1/cancel/token/
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که نوتیفیکیشن‌ها از آن زمان‌بندی شده‌اند. |
| `request_ids[]` | اجباری | UUID | لیست شناسه یکتای درخواست‌های زمان‌بندی‌شده. |

### نکات

- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای ارسال پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.
- نتیجهٔ درخواست (`status`) یکی از حالت‌های زیر است:
  - `InvalidID`: شناسهٔ یکتای فرآیند ارسال نامعتبر است.
  - `SentCompleted`: فرآیند ارسال تمام شده و امکان لغو وجود ندارد.
  - `Canceled`: لغو ارسال با موفقیت انجام شد.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |

### نمونه درخواست

```bash
curl --location 'https://push.najva.com/v1/cancel/token/' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'request_ids[]="4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c"' \
--form 'request_ids[]="9615c2ea-9d2d-4343-b880-4e79cb115384"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "21a4548a-574d-4425-9af2-6a0e70dae649",
    "result": [
      {
        "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
        "status": "InvalidID"
      },
      {
        "request_id": "9615c2ea-9d2d-4343-b880-4e79cb115384",
        "status": "Canceled"
      }
    ]
  }
}
```

---

## ۵. لغو پوش نوتیفیکیشن زمان‌بندی‌شده به همه توکن‌ها (broadcast)

کاربرد این متد لغو ارسال پوش نوتیفیکیشن از پیش زمان‌بندی‌شده به همهٔ توکن‌های مشتری است.

**ساختار URL (متد `POST`):**

```
https://push.najva.com/v1/cancel/bulk/
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که نوتیفیکیشن‌ها از آن زمان‌بندی شده‌اند. |
| `execution_ids[]` | اجباری | UUID | لیست شناسه یکتای فرآیند ارسال درخواست‌های زمان‌بندی‌شده. |

### نکات

- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای ارسال پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.
- نتیجهٔ درخواست (`status`): `InvalidID`، `SentCompleted` یا `Canceled` (مانند متد قبل).

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |

### نمونه درخواست

```bash
curl --location 'https://push.najva.com/v1/cancel/bulk/' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'execution_ids[]="4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c"' \
--form 'execution_ids[]="9615c2ea-9d2d-4343-b880-4e79cb115384"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "21a4548a-574d-4425-9af2-6a0e70dae649",
    "result": [
      {
        "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
        "status": "InvalidID"
      },
      {
        "request_id": "9615c2ea-9d2d-4343-b880-4e79cb115384",
        "status": "Canceled"
      }
    ]
  }
}
```

---

## ۶. دریافت گزارش ارسال به توکن خاص

کاربرد این متد دریافت گزارش ارسال پوش نوتیفیکیشن به توکن‌های خاص است. شناسهٔ درخواستی که از متدهای `send/token/` یا `send/peer/` دریافت کرده‌اید را به این متد بدهید.

**ساختار URL (متد `GET`):**

```
https://push.najva.com/v1/report/token
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که از آن نوتیفیکیشن‌ها ارسال شده‌اند. |
| `request_id` | اجباری | String | شناسه یکتای درخواست ارسال به توکن (`token/`) یا ارسال شخصی‌سازی‌شده (`peer/`). |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `request_id` | UUID | شناسه یکتای درخواست. |
| `tokens` | Array | لیست وضعیت ارسال به توکن‌های داده‌شده. |
| `token` | UUID | توکن مورد ارسال. |
| `status` | String | وضعیت ارسال به توکن مذکور. |
| `updated_time` | Time | زمان آخرین وضعیت دریافت‌شده برای توکن مذکور. |

### نکات

- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای دریافت گزارش پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |
| `414` | تعداد توکن‌های ارسال‌شده بیشتر از ۱۰۰۰ عدد است. |

### نمونه درخواست

```bash
curl --location --request GET 'https://push.najva.com/v1/report/token' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'request_id="4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
    "tokens": [
      {
        "token": "21a4548a-574d-4425-9af2-6a0e70dae649",
        "status": "INVALID_TOKEN",
        "updated_time": null
      },
      {
        "token": "9615c2ea-9d2d-4343-b880-4e79cb115384",
        "status": "START_TO_SEND",
        "updated_time": "2025-05-18T14:29:49.104577+03:30"
      }
    ]
  }
}
```

---

## ۷. دریافت گزارش ارسال به همه توکن‌ها (broadcast)

کاربرد این متد دریافت گزارش ارسال پوش نوتیفیکیشن به همهٔ توکن‌هاست.

**ساختار URL (متد `GET`):**

```
https://push.najva.com/v1/report/bulk
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر که از آن نوتیفیکیشن‌ها ارسال شده‌اند. |
| `execution_id` | اجباری | String | شناسه یکتای فرآیند ارسال به همه توکن‌ها (`bulk/`). |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `status` | String | وضعیت فرآیند ارسال. |
| `sent` | Integer | تعداد پیام‌های ارسال‌شده. |
| `delivered` | Integer | تعداد پیام‌های دریافت‌شده سمت کاربر. |
| `clicked` | Integer | تعداد کلیک روی پیام‌ها. |
| `showed` | Integer | تعداد پیام‌های مشاهده‌شده. |
| `failed` | Integer | تعداد پیام‌های ناموفق. |

### نکات

- وضعیت ارسال (`status`) یکی از حالت‌های `DRAFT`، `SCHEDULED`، `PENDING`، `RUNNING`، `COMPLETED` یا `CANCELED` است.
- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای دریافت گزارش پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |

### نمونه درخواست

```bash
curl --location --request GET 'https://push.najva.com/v1/report/bulk' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'execution_id="9615c2ea-9d2d-4343-b880-4e79cb115384"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "request_id": "4faac313-f3b2-4f5e-b9b9-dabc7e3f5d4c",
    "status": "COMPLETED",
    "sent": "1000",
    "delivered": "700",
    "click": "500",
    "preview": "400",
    "failed": "300",
    "send_datetime": "2025-05-18T14:29:49.104577+03:30",
    "send_now": "True"
  }
}
```

---

## ۸. دریافت پروفایل توکن‌ها

کاربرد این متد دریافت اطلاعات پروفایل توکن‌های خاص است. در این متد امکان دریافت اطلاعات چندین توکن وجود دارد؛ برای این کار تنها لازم است تمامی توکن‌های مورد نظر در پارامتر `tokens` قرار داده شوند.

**ساختار URL (متد `GET`):**

```
https://push.najva.com/v1/detail/token
```

### پارامترهای ورودی

| پارامتر | اجباری؟ | نوع | توضیحات |
|---|---|---|---|
| `website_id` | اجباری | Integer | شناسه اسکریپت پنل مورد نظر. |
| `tokens[]` | اجباری | String | به تعداد توکن‌های مورد نظر، از این پارامتر به درخواست افزوده می‌شود. |

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `token_profiles` | Array | لیست پروفایل توکن‌های درخواست‌شده. |
| `token` | UUID | توکن کوکی. |
| `ip` | String | آدرس IP کاربر. |
| `isp_type` | String | ISP کاربر. |
| `device_type` | String | دستگاه کاربر. |
| `browser_type` | String | مرورگر کاربر. |
| `os_type` | String | سیستم‌عامل کاربر. |
| `created` | String | تاریخ ایجاد توکن. |
| `modified` | String | آخرین تاریخ تغییر توکن. |

### نکات

- در هر درخواست مجاز به ارسال تا سقف **۱۰۰۰ توکن** هستید.
- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای دریافت گزارش پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `400` | پارامترهای ورودی صحیح نیستند. |
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |
| `414` | تعداد توکن‌های ارسال‌شده بیشتر از ۱۰۰۰ عدد است. |

### نمونه درخواست

```bash
curl --location --request GET 'https://push.najva.com/v1/detail/token' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}' \
--form 'website_id="45100"' \
--form 'tokens[]="21a4548a-574d-4425-9af2-6a0e70dae649"' \
--form 'tokens[]="9615c2ea-9d2d-4343-b880-4e79cb115384"'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "token_profiles": [
      {
        "token": "21a4548a-574d-4425-9af2-6a0e70dae649",
        "ip": "192.168.1.1",
        "isp_type": "ASIATECH",
        "device_type": "DESKTOP_WEB",
        "browser_type": "FIREFOX",
        "os_type": "WINDOWS",
        "created": "2025-05-18T14:29:49.104577+03:30",
        "modified": "2025-05-19T14:29:49.104577+05:30"
      }
    ]
  }
}
```

---

## ۹. دریافت وب‌سایت‌های کاربر

کاربرد این متد دریافت شناسهٔ وب‌سایت‌های کاربر در نجواست.

**ساختار URL (متد `GET`):**

```
https://push.najva.com/v1/sender
```

### پارامترهای ورودی

این متد پارامتر ورودی ندارد.

### پارامترهای خروجی

| پارامتر | نوع | توضیحات |
|---|---|---|
| `websites` | Array | لیست وب‌سایت‌های کاربر. |
| `id` | Integer | شناسه وب‌سایت. |
| `address` | String | آدرس وب‌سایت. |

### نکات

- برای احراز هویت، `apiKey` معتبر در header قرار دهید.
- برای دریافت گزارش پوش تراکنشی (با API) وایت‌لیست کردن IP الزامی است.

### جدول خطاها

| کد خطا | توضیح |
|---|---|
| `403` | نامعتبر بودن Api Key (عدم احراز هویت مناسب). |
| `416` | آدرس IP مبدأ مطابقت ندارد. |

### نمونه درخواست

```bash
curl --location --request GET 'https://push.najva.com/v1/sender' \
--header 'Content-Type: multipart/form-data' \
--header 'apiKey: {Api Key}'
```

### نمونه پاسخ

```json
{
  "Message": "Request approved.",
  "Entries": {
    "websites": [
      {
        "address": "https://najva.com",
        "id": "45290"
      },
      {
        "address": "https://test.com",
        "id": "53769"
      }
    ]
  }
}
```

---

## پیوست: اصلاحات و ناسازگاری‌های موجود در سند اصلی

در تبدیل این سند، موارد زیر در PDF اصلی دیده شد و در این نسخه به‌صورت زیر برطرف شده است. پیش از استفاده، با پشتیبانی نجوا تأیید کنید.

| مورد | در PDF اصلی | در این نسخه |
|---|---|---|
| نام پارامترها در جداول | `id_website`، `id_request`، `title.message` و … (به‌دلیل استخراج معکوس متن فارسی/انگلیسی) | مطابق نمونه‌های curl: `website_id`، `request_id`، `message.title` و … |
| پارامتر زمان‌بندی در ارسال broadcast | جدول: `date`؛ نمونه curl: `datetime` (با مقدار ناقص `025-07-21…`) | `date` با مقدار اصلاح‌شدهٔ `2025-07-21…` |
| آدرس نمونه لغو broadcast | `/v1/cancel/token/` | `/v1/cancel/bulk/` (مطابق ساختار URL ذکرشده) |
| نام پارامتر لغو | جدول: `ids_request` / `ids_execution`؛ نمونه: `request_ids[]` / `execution_ids[]` | نام‌های نمونه curl |
| فیلدهای گزارش broadcast | جدول: `clicked`، `showed`؛ نمونه پاسخ: `click`، `preview` | هر دو در متن آمده‌اند؛ نام دقیق را از پاسخ واقعی سرور بررسی کنید. |
| آدرس‌های ناقص در curl | چند نمونه بدون بستن `'` | بسته شده است. |
| فیلدهای ارسال شخصی‌سازی‌شده | جدول: `messages[n].token`؛ نمونه: `messages.token[]` | نمونهٔ curl |
