import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from utils.sms import SMSService


class Command(BaseCommand):
    help = "ارسال پیامک تستی با کلید فعال سامانه"

    def add_arguments(self, parser):
        parser.add_argument("mobile", type=str, help="شماره موبایل مقصد (مثلاً 09123456789)")
        parser.add_argument(
            "--pattern",
            type=str,
            choices=["otp", "invoice", "text"],
            default="otp",
            help="نوع ارسال: otp (کد تایید)، invoice (پیش‌فاکتور با لینک)، text (متن عادی)",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="تایید خودکار بدون پرسیدن سوال در ترمینال",
        )

    def handle(self, *args, **options):
        mobile = options["mobile"]
        pattern = options["pattern"]
        auto_yes = options["yes"]

        api_key = getattr(settings, "SMS_IR_API_KEY", "")
        masked_key = f"{api_key[:4]}..." if api_key else "NOT SET"

        self.stdout.write(f"کلید فعال SMS.ir: {masked_key}")

        if not api_key:
            self.stdout.write(self.style.ERROR("کلید SMS_IR_API_KEY تنظیم نشده است."))
            return

        if not auto_yes:
            confirm = input(f"پیامک با کلید واقعی ({masked_key}) به شماره {mobile} ارسال می‌شود. ادامه می‌دهید؟ (y/N): ")
            if confirm.lower() != "y":
                self.stdout.write("ارسال لغو شد.")
                return

        sms = SMSService()
        if pattern == "otp":
            self.stdout.write("در حال ارسال پترن OTP با کد 12345...")
            result = sms.send_otp(mobile=mobile, code="12345")
        elif pattern == "invoice":
            self.stdout.write("در حال ارسال پترن فاکتور با لینک ساختگی s/testcode/...")
            result = sms.send_invoice_issued(
                mobile=mobile,
                name="تست",
                number="INV-TEST",
                username="test",
                password="Test1234",
                link="s/testcode/",
            )
        elif pattern == "text":
            self.stdout.write("در حال ارسال پیامک متنی آزاد...")
            result = sms.send_text(mobile=mobile, message="تست سامانه فرابخش")

        self.stdout.write("\n=== نتیجه ارسال ===")
        self.stdout.write(f"success: {result.get('success')}")
        self.stdout.write(f"error: {result.get('error')}")
        self.stdout.write(f"data: {result.get('data')}")
