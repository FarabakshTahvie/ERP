import uuid
from urllib.parse import urlsplit

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from filemanager import storage

COMBOS = [("path", "s3v4"), ("virtual", "s3v4"), ("path", "s3"), ("virtual", "s3")]


class Command(BaseCommand):
    help = "تست اتصال به فضای ابری آروان برای فایل‌منیجر: نوشتن، خواندن و حذف یک فایل آزمایشی."

    def handle(self, *args, **options):
        s = settings
        names = {"ARVANCLOUD_ACCESS_KEY_ID": s.ARVAN_FILES_ACCESS_KEY,
                 "ARVANCLOUD_SECRET_ACCESS_KEY": s.ARVAN_FILES_SECRET_KEY,
                 "ARVANCLOUD_STORAGE_BUCKET_NAME": s.ARVAN_FILES_BUCKET,
                 "ARVANCLOUD_S3_ENDPOINT_URL": s.ARVAN_FILES_ENDPOINT}
        for name, value in names.items():
            self.stdout.write(f"{name}: {'پر است (طول ' + str(len(value)) + ')' if value else 'خالی است'}")
        empty = [n for n, v in names.items() if not v]
        if empty:
            raise CommandError("این متغیرها در .env خالی‌اند: " + "، ".join(empty))

        parts = urlsplit(s.ARVAN_FILES_ENDPOINT)
        bucket = s.ARVAN_FILES_BUCKET
        if parts.scheme != "https" or parts.path not in ("", "/"):
            self.stdout.write(self.style.WARNING("آدرس endpoint باید فقط دامنه باشد، مثل https://s3.ir-thr-at1.arvanstorage.ir (بدون نام باکت)."))
        if "/" in bucket or "://" in bucket or " " in bucket:
            self.stdout.write(self.style.WARNING("نام باکت باید فقط خود نام باشد، بدون آدرس یا اسلش."))

        current = (s.ARVAN_FILES_ADDRESSING_STYLE, s.ARVAN_FILES_SIGNATURE)
        working = None
        for addressing, signature in [current] + [c for c in COMBOS if c != current]:
            error = self._probe(addressing, signature)
            if error is None:
                self.stdout.write(self.style.SUCCESS(f"✔ addressing={addressing} signature={signature} — نوشتن، خواندن و حذف موفق"))
                working = (addressing, signature)
                break
            self.stdout.write(self.style.ERROR(f"✘ addressing={addressing} signature={signature} — {error}"))

        if working is None:
            raise CommandError(
                "هیچ ترکیبی جواب نداد. علت‌های رایج ۴۰۱ و ۴۰۳: کلید دسترسی به همین باکت اجازه‌ی نوشتن ندارد؛ "
                "نام باکت یا endpoint اشتباه است؛ فاصله یا کاراکتر اضافه کنار مقدارها هست؛ "
                "ساعت دستگاه (RequestTimeTooSkewed) عقب یا جلو است.")
        if working != current:
            self.stdout.write(self.style.WARNING(
                f"تنظیم فعلی جواب نمی‌دهد ولی این ترکیب جواب می‌دهد: ARVAN_FILES_ADDRESSING_STYLE={working[0]} "
                f"و ARVAN_FILES_SIGNATURE={working[1]}. مقدار default در settings.py را همین بگذار."))

    def _probe(self, addressing, signature):
        bucket = settings.ARVAN_FILES_BUCKET
        key = f"filemanager/_check/{uuid.uuid4().hex}.txt"
        client = storage.build_client(addressing=addressing, signature=signature)
        step, deleted = "write", False
        try:
            client.put_object(Bucket=bucket, Key=key, Body=b"ok", ContentType="text/plain")
            step = "read"
            if client.get_object(Bucket=bucket, Key=key)["Body"].read() != b"ok":
                return "read: محتوای خوانده‌شده با نوشته‌شده یکی نیست"
            step = "delete"
            client.delete_object(Bucket=bucket, Key=key)
            deleted = True
            return None
        except ClientError as exc:
            err = exc.response.get("Error", {})
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            return f"{step}: HTTP {status} {err.get('Code', '')} {str(err.get('Message', ''))[:100]}".strip()
        except BotoCoreError as exc:
            return f"{step}: {type(exc).__name__}"
        finally:
            if not deleted:
                try:
                    client.delete_object(Bucket=bucket, Key=key)
                except Exception:
                    pass
