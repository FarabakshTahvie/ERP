import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "بررسی وضعیت اتصال به API رسمی sms.ir (اعتبار حساب، خطوط فعال و کلید)"

    def handle(self, *args, **options):
        api_key = getattr(settings, "SMS_IR_API_KEY", "")
        if not api_key:
            self.stdout.write(self.style.ERROR("کلید SMS_IR_API_KEY تنظیم نشده است."))
            return

        masked_key = f"{api_key[:4]}..."
        self.stdout.write(f"چهار کاراکتر اول کلید: {masked_key}")

        headers = {
            "X-API-KEY": api_key,
            "Accept": "application/json",
        }

        # 1. استعلام اعتبار حساب از https://api.sms.ir/v1/credit
        self.stdout.write("\n1. در حال استعلام اعتبار حساب (GET /v1/credit)...")
        try:
            r_credit = requests.get("https://api.sms.ir/v1/credit", headers=headers, timeout=10)
            data_credit = r_credit.json()
            if r_credit.status_code == 200 and data_credit.get("status") == 1:
                credit_val = data_credit.get("data")
                self.stdout.write(self.style.SUCCESS(f"اعتبار حساب: {credit_val}"))
            else:
                err_msg = data_credit.get("message") or f"HTTP {r_credit.status_code}"
                self.stdout.write(self.style.ERROR(f"خطا در دریافت اعتبار: {err_msg}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"خطای شبکه در دریافت اعتبار: {e}"))

        # 2. استعلام لیست خطوط از https://api.sms.ir/v1/line
        self.stdout.write("\n2. در حال استعلام لیست خطوط (GET /v1/line)...")
        try:
            r_line = requests.get("https://api.sms.ir/v1/line", headers=headers, timeout=10)
            data_line = r_line.json()
            if r_line.status_code == 200 and data_line.get("status") == 1:
                lines = data_line.get("data")
                self.stdout.write(self.style.SUCCESS(f"فهرست خط‌ها: {lines}"))
            else:
                err_msg = data_line.get("message") or f"HTTP {r_line.status_code}"
                self.stdout.write(self.style.ERROR(f"خطا در دریافت خطوط: {err_msg}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"خطای شبکه در دریافت خطوط: {e}"))
