# قالب در انتظار ساخت در پنل sms.ir (پیشنهاد در docs/SMS_TEMPLATES.md):
# visit_scheduled(name,date)
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
    "payment_confirmed": {
        "pattern_code": "666482",
        "parameters": ["name", "number", "remaining", "LINK"],
        "reference_text": (
            "سلام %name%\nپرداخت شما برای فاکتور %number% تایید شد.\n"
            "مانده فاکتور: %remaining% تومان\nfarabakhshtahvieh.com/%LINK%\nفرابخش تهویه"
        ),
    },
    "payment_rejected": {
        "pattern_code": "586652",
        "parameters": ["name", "number", "LINK"],
        "reference_text": (
            "سلام %name%\nپرداخت ثبت‌شده برای فاکتور %number% تایید نشد؛ "
            "دلیل را در پرتال ببینید و دوباره ثبت کنید.\n"
            "لینک: farabakhshtahvieh.com/%LINK%\nفرابخش تهویه"
        ),
    },
}
