# قالب‌های در انتظار ساخت در پنل sms.ir (پیشنهادها در docs/SMS_TEMPLATES.md):
# visit_scheduled(name,date) · design_approval_request(name,LINK) ·
# payment_confirmed(name,number,remaining) · payment_rejected(name,number,LINK)
"""
رجیستری تمپلیت‌های تاییدشده در پنل sms.ir. هر تمپلیت جدید فقط یک ورودی
به این دیکشنری اضافه می‌شه. پارامترها باید دقیقاً با چیزی که در پنل sms.ir
برای اون کد تعریف شده مطابقت داشته باشه.
"""

SMS_PATTERNS = {
    "invoice_issued_with_credentials": {
        "pattern_code": "238198",
        "parameters": ["name", "number", "username", "password", "LINK"],
        "reference_text": (
            "سلام %name%\nپیش‌فاکتور شما به شماره %number% ثبت شد.\n"
            "یوزرنیم: %username%\nپسورد: %password%\n"
            "لینک: farabakhshtahvieh.com/%LINK%\nفرابخش تهویه"
        ),
    },
    "login_otp": {
        "pattern_code": "673093",
        "parameters": ["code"],
        "reference_text": "کد ورود شما: %code%\nفرابخش تهویه\nfarabakhshtahvieh.com",
    },
}
