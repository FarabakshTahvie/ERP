# Media Chrome (پخش‌کننده‌ی پیام‌رسان)

- نسخه: 4.19.3 (بسته‌ی npm با نام `media-chrome`، ساخته‌ی Mux)
- مجوز: MIT
- فایل: `static/js/vendor/media-chrome.js` (یک فایل واحد IIFE؛ فقط در صفحه‌ی چت پیام‌رسان لود می‌شود)
- CDN نداریم؛ فایل کامل روی سرور خودمان است.

## ساخت دوباره یا به‌روزرسانی
در یک پوشه‌ی موقت بیرون از ریپو:

```bash
npm init -y && npm i media-chrome@<نسخه> esbuild
echo "import 'media-chrome';" > entry.js
npx esbuild entry.js --bundle --minify --format=iife --target=es2020 --legal-comments=inline \
  --banner:js="/* media-chrome <نسخه> (MIT), esbuild bundle. docs/vendor/media-chrome.md */" \
  --outfile=media-chrome.js
```

فایل خروجی را جای `static/js/vendor/media-chrome.js` بگذار، نسخه‌ی بالای همین فایل را عوض کن و ظاهر پخش‌کننده را در حالت روشن و تاریک ببین.

## نکته‌ها
- رنگ‌ها با متغیرهای `--media-*` در `static/src/input.css` (کلاس `msgr-player`) از تم می‌آید.
- اگر این فایل لود نشود، `messenger_media.js` به پخش‌کننده‌ی خود مرورگر برمی‌گردد.
- برچسب‌های دسترس‌پذیری کتابخانه انگلیسی است؛ متن‌های راهنمای روی دکمه‌ها (tooltip) پنهان شده‌اند.
