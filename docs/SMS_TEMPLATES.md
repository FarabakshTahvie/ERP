# قالب‌های پیشنهادی پیامک (SMS.ir Patterns)

| نام رویداد | نام الگو در کد | پارامترها | متن پیشنهادی |
| --- | --- | --- | --- |
| زمان بازدید | `visit_scheduled` | `name`, `date` | سلام %name%، تاریخ بازدید پروژه شما برای روز %date% تنظیم شد. فرابخش تهویه |
| تایید طرح | `design_approval_request` | `name`, `LINK` | سلام %name%، طرح جدید پروژه آماده تایید است. لینک: farabakhshtahvieh.com/%LINK% |
| تایید پرداخت | `payment_confirmed` | `name`, `number`, `remaining` | سلام %name%، پرداخت شما برای پیش‌فاکتور %number% تایید شد. مانده: %remaining% |
| رد پرداخت | `payment_rejected` | `name`, `number`, `LINK` | سلام %name%، رسید پرداخت پیش‌فاکتور %number% نیازمند بررسی مجدد است. لینک: farabakhshtahvieh.com/%LINK% |
