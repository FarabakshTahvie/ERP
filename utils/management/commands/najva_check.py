import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from utils.push_notification import NajvaService


class Command(BaseCommand):
    help = "بررسی تنظیمات و اتصال به سرویس نجوا"

    def handle(self, *args, **options):
        api_key = getattr(settings, "NAJVA_API_KEY", "")
        website_id = getattr(settings, "NAJVA_WEBSITE_ID", "")

        masked_key = f"{api_key[:4]}... (length: {len(api_key)})" if api_key else "NOT SET"
        self.stdout.write(f"NAJVA_API_KEY: {masked_key}")
        self.stdout.write(f"NAJVA_WEBSITE_ID: {website_id or 'NOT SET'}")

        # گرفتن IP خروجی
        try:
            ip_resp = requests.get("https://api.ipify.org", timeout=5)
            server_ip = ip_resp.text.strip()
            self.stdout.write(f"IP خروجی سرور: {server_ip}")
        except Exception as e:
            server_ip = "نامشخص"
            self.stdout.write(self.style.WARNING(f"عدم امکان دریافت IP سرور: {e}"))

        if not api_key:
            self.stdout.write(self.style.ERROR("کلید NAJVA_API_KEY تنظیم نشده است."))
            return

        service = NajvaService()
        result = service.list_websites()
        if not result.get("success"):
            status_code = result.get("status_code")
            error = result.get("error")
            self.stdout.write(self.style.ERROR(f"خطا در دریافت اطلاعات از نجوا (کد {status_code}): {error}"))
            if status_code == 416:
                self.stdout.write(self.style.ERROR(f"این IP ({server_ip}) را در پنل نجوا وایت‌لیست کن."))
            return

        websites = result.get("websites", [])
        self.stdout.write(self.style.SUCCESS(f"تعداد وب‌سایت‌های یافت‌شده: {len(websites)}"))
        for w in websites:
            w_id = w.get("id")
            w_addr = w.get("address", "")
            self.stdout.write(f" - ID: {w_id} | آدرس: {w_addr}")
            if "farabakhshtahvie.com" not in w_addr:
                self.stdout.write(self.style.WARNING(f"   [هشدار] آدرس وب‌سایت '{w_addr}' با farabakhshtahvie.com مطابقت ندارد!"))
