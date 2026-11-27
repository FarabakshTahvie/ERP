from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from utils import db_backup


class Command(BaseCommand):
    help = ("بکاپ دیتابیس: dump فشرده روی سرور (۱۴ روز) و آپلود به باکت جدای آروان (۲ روز). "
            "بدون گزینه = بکاپ کامل. media بکاپ گرفته نمی‌شود.")

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--local-only", action="store_true", help="فقط روی سرور؛ بدون آپلود")
        mode.add_argument("--check", action="store_true", help="تست اتصال به باکت بکاپ (نوشتن، خواندن، حذف)")
        mode.add_argument("--list", action="store_true", help="فهرست بکاپ‌های سرور و ابر")
        mode.add_argument("--download", metavar="KEY_OR_latest", help="دانلود یک بکاپ از ابر")
        parser.add_argument("--to", help="مسیر فایل مقصد برای --download")

    def handle(self, *args, **opts):
        try:
            if opts["check"]:
                self._check()
            elif opts["list"]:
                self._list()
            elif opts["download"]:
                if not opts["to"]:
                    raise CommandError("همراه --download باید --to هم بدهید.")
                path = db_backup.cloud_download(opts["download"], opts["to"])
                self.stdout.write(self.style.SUCCESS(f"دانلود شد: {path}"))
            else:
                db_backup.run_backup(local_only=opts["local_only"], say=self.stdout.write)
                self.stdout.write(self.style.SUCCESS("بکاپ کامل شد."))
        except db_backup.BackupError as exc:
            raise CommandError(str(exc))

    def _check(self):
        s = settings
        for name, value in (("BACKUP_CLOUD_ACCESS_KEY_ID", s.BACKUP_CLOUD_ACCESS_KEY),
                            ("BACKUP_CLOUD_SECRET_ACCESS_KEY", s.BACKUP_CLOUD_SECRET_KEY),
                            ("BACKUP_CLOUD_BUCKET_NAME", s.BACKUP_CLOUD_BUCKET),
                            ("BACKUP_CLOUD_ENDPOINT_URL", s.BACKUP_CLOUD_ENDPOINT)):
            self.stdout.write(f"{name}: {'پر است (طول ' + str(len(value)) + ')' if value else 'خالی است'}")
        db_backup.cloud_check()
        self.stdout.write(self.style.SUCCESS("اتصال به باکت بکاپ درست است: نوشتن، خواندن و حذف موفق."))
        self._list_cloud()

    def _list(self):
        folder = Path(settings.BACKUP_DIR)
        self.stdout.write(f"روی سرور ({folder}):")
        try:
            rows = sorted((p for p in folder.iterdir() if p.is_file() and db_backup.NAME_RE.match(p.name)), reverse=True)
        except OSError:
            self.stdout.write("  پوشه در دسترس نیست (هنوز بکاپی گرفته نشده یا دسترسی ندارید).")
            rows = []
        for p in rows:
            self.stdout.write(f"  {p.name}  {db_backup._mb(p.stat().st_size)}")
        if not rows:
            self.stdout.write("  (خالی)")
        if db_backup_ready(self):
            self._list_cloud()

    def _list_cloud(self):
        self.stdout.write("روی ابر آروان:")
        rows = db_backup.cloud_list()
        for key, size in rows:
            self.stdout.write(f"  {key}  {db_backup._mb(size)}")
        if not rows:
            self.stdout.write("  (خالی)")


def db_backup_ready(command):
    try:
        db_backup.assert_cloud_ready()
    except db_backup.BackupError as exc:
        command.stdout.write(f"ابر: {exc}")
        return False
    return True
