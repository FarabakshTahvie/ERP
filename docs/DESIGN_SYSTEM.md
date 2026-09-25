# قوانین دیزاین سیستم فرابخش
1. کارت = `fb-card fb-pad`. صفحه = `fb-page` (با `--sm` / `--lg`). پنل داخلی = `fb-inset`.
2. روی `fb-*` هیچ `rounded-*` / `shadow-*` اضافه نشود. سایه فقط برای منو، توست و مودال.
3. دکمه: در هر ناحیه یک `btn-primary`؛ بقیه `btn-soft` یا `btn-ghost`؛ رد/حذف: `btn-soft btn-error`. روی دکمه‌ها `rounded-*`، `shadow-*`، `h-*` ننویسید.
4. فرم: `fb-field` + `fb-label` + کنترل `input|select|textarea|file-input` با `w-full` (بدون `-bordered`). خطا: `input-error` + `fb-error`.
5. هشدار: همیشه `alert alert-soft alert-*`؛ کلاس `text-*-content` داخلش نگذارید.
6. بج: فقط `fb-badge fb-badge-*`. تب: `tabs tabs-border`.
7. تایپوگرافی: عنوان صفحه `fb-page-title`، عنوان بخش `fb-section-title`، متن `text-sm`، متادیتا `text-xs fb-muted`. `font-black` ممنوع.
8. آیکون: `w-4 h-4` داخل دکمه/متن، `w-5 h-5` مستقل؛ بزرگ‌تر فقط در حالت خالی.
9. اعداد و تلفن: `font-technical`. ورودی مخفی داخل `fb-choice`: `sr-only` نه `hidden`.
10. کلاس‌های حذف‌شده در daisyUI 5 ممنوع: `*-bordered`، `form-control`، `label-text`، `tabs-boxed`، `*-focus`.
11. `font-technical` (چون `direction: ltr` دارد) فقط روی عنصر درون‌خطی (`span`/`a`/`input`) بنشیند. روی بلوک (`div`/`td`) بلوک را به چپ می‌چسباند؛ کنارش `text-right` یا `text-center` بنویسید.
12. گوشه‌گردی: فقط `rounded-field` (کنترل، چیپ، لوگو) و `rounded-box` (کارت سفارشی). `rounded-xl/2xl/3xl` ممنوع.
13. کلاس‌های حذف‌شده‌ی Tailwind v4: `flex-shrink-0` (→ `shrink-0`)، `flex-grow` (→ `grow`)، `bg-opacity-*` و `text-opacity-*` (→ `/50`).
14. رنگ وضعیت‌ها در همه‌ی صفحات یکسان است:
    - پروژه: پیش‌نویس neutral، در حال اجرا info، تکمیل‌شده success، لغو‌شده error.
    - مرحله: در انتظار neutral، در حال انجام info، در انتظار تایید warning، رد شده/معلق error، انجام‌شده success.
    - زرد (warning) فقط برای چیزی است که منتظر اقدام کسی است.
15. آکاردئون: `collapse collapse-arrow bg-base-100 border border-base-300` (استثنای قانون ۱).
16. فرم‌های بلند: دکمه‌ی ثبت داخل `fb-sticky-bar` در انتهای فرم قرار می‌گیرد.
17. جدول‌های لیستی فقط با موتور `generic_table` ساخته می‌شوند؛ ریشه‌ی آن `fb-card` است و تب‌پنل کارت نمی‌سازد.
18. ورودی مخفی داخل `fb-choice` همیشه `sr-only` است؛ `hidden` ممنوع (فوکوس کیبورد را از بین می‌برد).
19. `space-y-*` به آخرین فرزندِ مخفی یا خالی هم فاصله می‌دهد و ته کارت را باز می‌کند؛ وقتی آخرین فرزند `hidden` یا خالی می‌شود از `flex flex-col gap-*` استفاده کنید. روی عنصری که خودش `hidden` می‌گیرد، `flex` ننویسید.
20. خط زمانی مراحل فقط با `fb-timeline` / `fb-timeline-item` / `fb-dot` (+`-done` `-active` `-warn`) ساخته می‌شود؛ `steps` قدیمی daisyUI ممنوع.
21. `font-technical` فقط دور خودِ عدد یا کد (تلفن، مبلغ، شماره فاکتور) بیاید، نه دور جمله‌ی فارسی که عدد دارد (جهت متن به‌هم می‌ریزد).
22. در فرمی که فیلد `required` دارد و دکمه‌ی «رد» هم در آن است، دکمه‌ی رد `formnovalidate` بگیرد.
23. فرمی که نباید دوبار ارسال شود `data-fb-once` می‌گیرد (قفل خودکار دکمه‌ها در base.html)؛ سمت سرور هم باید ایمن بماند.
