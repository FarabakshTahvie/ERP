"""
بکاپ دیتابیس: dump فشرده روی سرور (۱۴ روز) + نسخه‌ی ابری روی باکت جدای آروان (۲ روز). media عمداً نیست.

ترتیب ایمنی: اول dump سالم، بعد حذف قدیمی‌های سرور، بعد آپلود و برابری حجم، و فقط بعدش حذف قدیمی‌های ابر.
پنجره‌ی نگه‌داری از «تازه‌ترین بکاپ» حساب می‌شود نه از ساعت سیستم؛ اگر بکاپ‌گیری متوقف شود
آخرین بکاپ‌ها پاک نمی‌شوند. فقط فایل‌هایی با نام db-YYYYMMDD-HHMM.dump دست می‌خورند.
"""
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:   # ویندوز؛ قفل اجرای هم‌زمان فقط روی سرور لینوکس لازم است
    fcntl = None

PREFIX = "database/"
NAME_RE = re.compile(r"^db-(\d{8})-(\d{4})\.dump$")
PART_SUFFIX = ".part"
DUMP_TIMEOUT = 6 * 3600
PART_SIZE = 64 * 1024 * 1024


class BackupError(Exception):
    """خطای بکاپ؛ پیامش فارسی است و هرگز رمز یا کلید ندارد."""


def _mb(n):
    return f"{n / 1024 / 1024:.1f}MB"


# ---------- قاعده‌ی نگه‌داری (توابع خالص) ----------
def parse_day(name):
    """تاریخ از نام db-YYYYMMDD-HHMM.dump؛ نام یا تاریخ نامعتبر ← None."""
    m = NAME_RE.match(name or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def plan_local_prune(names, keep_days):
    """نام فایل‌هایی که باید پاک شوند. پنجره: keep_days روز تقویمی تا تازه‌ترین بکاپ (خودش هم حساب است)."""
    if keep_days < 1:
        raise ValueError("keep_days باید حداقل ۱ باشد.")
    dated = {n: parse_day(n) for n in names}
    dated = {n: d for n, d in dated.items() if d is not None}
    if not dated:
        return []
    cutoff = max(dated.values()) - timedelta(days=keep_days - 1)
    return sorted(n for n, d in dated.items() if d < cutoff)


def _cloud_items(keys):
    items = []
    for key in keys:
        if not key.startswith(PREFIX):
            continue
        base = key[len(PREFIX):]
        m = NAME_RE.match(base)
        if m and parse_day(base):
            items.append((m.group(1), m.group(2), key))
    return sorted(items, reverse=True)


def plan_cloud_prune(keys, keep_days):
    """کلیدهایی که باید پاک شوند: از هر یک از keep_days روز آخر، تازه‌ترین فایل می‌ماند."""
    if keep_days < 1:
        raise ValueError("keep_days باید حداقل ۱ باشد.")
    items = _cloud_items(keys)
    kept_days, keep = [], set()
    for day, _hm, key in items:
        if day in kept_days:
            continue
        if len(kept_days) < keep_days:
            kept_days.append(day)
            keep.add(key)
    return sorted(key for _d, _h, key in items if key not in keep)


# ---------- قفل اجرای هم‌زمان ----------
class _Lock:
    def __init__(self, directory):
        self.path = Path(directory) / ".lock"
        self.fh = None

    def __enter__(self):
        if fcntl is None:
            return self
        self.fh = open(self.path, "w")
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.fh.close()
            self.fh = None
            raise BackupError("بکاپ دیگری همین الان در حال اجراست.")
        return self

    def __exit__(self, *exc):
        if self.fh:
            self.fh.close()   # قفل با بستن فایل آزاد می‌شود


# ---------- dump روی سرور ----------
def _run(cmd, *, what, env=None, discard_stdout=False):
    try:
        result = subprocess.run(
            cmd, env=env, stdout=subprocess.DEVNULL if discard_stdout else None,
            stderr=subprocess.PIPE, text=True, timeout=DUMP_TIMEOUT)
    except FileNotFoundError:
        raise BackupError(f"برنامه‌ی {what} روی سرور پیدا نشد.")
    except subprocess.TimeoutExpired:
        raise BackupError(f"{what} بیش از حد طول کشید و متوقف شد.")
    if result.returncode != 0:
        tail = (result.stderr or "").strip()[-300:]
        raise BackupError(f"{what} ناموفق بود (کد {result.returncode}): {tail}")


def dump_database(dest, *, db=None, now=None):
    """dump فشرده را اول در فایل .part می‌سازد، سالم‌بودن فهرستش را با pg_restore می‌سنجد و بعد با نام نهایی منتشر می‌کند.
    رمز فقط از راه PGPASSWORD می‌رود، نه خط فرمان. خروجی: مسیر فایل نهایی."""
    db = db or settings.DATABASES["default"]
    if "postgresql" not in str(db.get("ENGINE", "")):
        raise BackupError("بکاپ فقط برای PostgreSQL ساخته شده است.")
    dest = Path(dest)
    stamp = (now or timezone.localtime()).strftime("%Y%m%d-%H%M")
    final = dest / f"db-{stamp}.dump"
    part = final.with_name(final.name + PART_SUFFIX)
    if final.exists():
        raise BackupError(f"فایل {final.name} از قبل هست؛ یک دقیقه بعد دوباره اجرا کنید.")
    cmd = ["pg_dump", "--format=custom", "--compress=6", "--no-password", "--file", str(part),
           "--host", str(db.get("HOST") or "127.0.0.1"), "--port", str(db.get("PORT") or 5432),
           "--username", str(db["USER"]), "--dbname", str(db["NAME"])]
    env = {**os.environ, "PGPASSWORD": str(db.get("PASSWORD") or "")}
    try:
        _run(cmd, what="pg_dump", env=env)
        if not part.is_file() or part.stat().st_size == 0:
            raise BackupError("فایل بکاپ خالی است.")
        _run(["pg_restore", "--list", str(part)], what="pg_restore", discard_stdout=True)
        os.replace(part, final)
    finally:
        part.unlink(missing_ok=True)
    return final


def prune_local(dest, keep_days):
    dest = Path(dest)
    doomed = plan_local_prune([p.name for p in dest.iterdir() if p.is_file()], keep_days)
    for name in doomed:
        (dest / name).unlink()
    return doomed


# ---------- ابر آروان ----------
def assert_cloud_ready():
    missing = [name for name, value in (
        ("BACKUP_CLOUD_ACCESS_KEY_ID", settings.BACKUP_CLOUD_ACCESS_KEY),
        ("BACKUP_CLOUD_SECRET_ACCESS_KEY", settings.BACKUP_CLOUD_SECRET_KEY),
        ("BACKUP_CLOUD_BUCKET_NAME", settings.BACKUP_CLOUD_BUCKET),
        ("BACKUP_CLOUD_ENDPOINT_URL", settings.BACKUP_CLOUD_ENDPOINT)) if not value]
    if missing:
        raise BackupError("این متغیرها در .env خالی‌اند: " + "، ".join(missing))
    if settings.BACKUP_CLOUD_BUCKET == settings.ARVAN_FILES_BUCKET:
        raise BackupError("باکت بکاپ باید جدا از باکت فایل‌منیجر باشد.")


def build_client():
    import boto3
    from botocore.config import Config
    cfg = Config(
        signature_version=settings.ARVAN_FILES_SIGNATURE,
        s3={"addressing_style": settings.ARVAN_FILES_ADDRESSING_STYLE},
        connect_timeout=10, read_timeout=120, retries={"max_attempts": 5, "mode": "standard"},
        # botocore جدید پیش‌فرض چک‌سام CRC32 می‌فرستد و بعضی S3های سازگار آن را رد می‌کنند
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )
    return boto3.client(
        "s3", endpoint_url=settings.BACKUP_CLOUD_ENDPOINT,
        aws_access_key_id=settings.BACKUP_CLOUD_ACCESS_KEY,
        aws_secret_access_key=settings.BACKUP_CLOUD_SECRET_KEY,
        region_name=settings.ARVAN_FILES_REGION or None, config=cfg)


def _cloud_call(action, fn, *args, **kwargs):
    """خطای ابر را به BackupError فارسی تبدیل می‌کند؛ فقط کد خطا، بدون کلید."""
    from boto3.exceptions import S3UploadFailedError
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        return fn(*args, **kwargs)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        logger.error("backup cloud %s failed: http=%s code=%s", action, status, code)
        raise BackupError(f"{action} در ابر ناموفق بود (HTTP {status} {code}).") from exc
    except (BotoCoreError, S3UploadFailedError) as exc:
        logger.error("backup cloud %s failed: %s", action, type(exc).__name__)
        raise BackupError(f"{action} در ابر ناموفق بود ({type(exc).__name__}).") from exc


def _list_objects(client):
    def work():
        out = []
        pages = client.get_paginator("list_objects").paginate(Bucket=settings.BACKUP_CLOUD_BUCKET, Prefix=PREFIX)
        for page in pages:
            out.extend(page.get("Contents", []))
        return out
    return _cloud_call("فهرست‌گرفتن", work)


def cloud_list(client=None):
    """[(key, size)] فقط بکاپ‌های خودمان، تازه‌ترین اول."""
    assert_cloud_ready()
    client = client or build_client()
    rows = [(o["Key"], o["Size"]) for o in _list_objects(client)]
    return sorted((r for r in rows if r[0].startswith(PREFIX) and NAME_RE.match(r[0][len(PREFIX):])), reverse=True)


def cloud_check(client=None):
    """نوشتن، خواندن و حذف یک فایل آزمایشی؛ برای دیدن درستی کلید و باکت."""
    assert_cloud_ready()
    client = client or build_client()
    bucket = settings.BACKUP_CLOUD_BUCKET
    key = f"{PREFIX}_check/{uuid.uuid4().hex}.txt"
    _cloud_call("نوشتن", client.put_object, Bucket=bucket, Key=key, Body=b"ok", ContentType="text/plain")
    try:
        body = _cloud_call("خواندن", lambda: client.get_object(Bucket=bucket, Key=key)["Body"].read())
        if body != b"ok":
            raise BackupError("محتوای خوانده‌شده با نوشته‌شده یکی نیست.")
    finally:
        _cloud_call("حذف", client.delete_object, Bucket=bucket, Key=key)


def cloud_upload(path, *, client=None, keep_days=None):
    """آپلود، برابری حجم، و فقط بعدش حذف قدیمی‌ها. فایل تازه هرگز پاک نمی‌شود. خروجی: {key, size, deleted}."""
    assert_cloud_ready()
    path = Path(path)
    if not NAME_RE.match(path.name) or parse_day(path.name) is None:
        raise BackupError("نام فایل بکاپ معتبر نیست (db-YYYYMMDD-HHMM.dump).")
    if not path.is_file() or path.stat().st_size == 0:
        raise BackupError("فایل بکاپ پیدا نشد یا خالی است.")
    from boto3.s3.transfer import TransferConfig
    size, key = path.stat().st_size, PREFIX + path.name
    client = client or build_client()
    bucket = settings.BACKUP_CLOUD_BUCKET
    transfer = TransferConfig(multipart_threshold=PART_SIZE, multipart_chunksize=PART_SIZE, max_concurrency=2)
    _cloud_call("آپلود", client.upload_file, str(path), bucket, key,
                ExtraArgs={"ContentType": "application/octet-stream"}, Config=transfer)
    remote = _cloud_call("راستی‌آزمایی حجم", client.head_object, Bucket=bucket, Key=key)["ContentLength"]
    if remote != size:
        try:
            _cloud_call("حذف فایل ناقص", client.delete_object, Bucket=bucket, Key=key)
        except BackupError:
            pass
        raise BackupError(f"حجم فایل در ابر ({remote}) با فایل سرور ({size}) یکی نیست؛ چیزی پاک نشد.")
    days = settings.BACKUP_CLOUD_KEEP_DAYS if keep_days is None else keep_days
    keys = [o["Key"] for o in _list_objects(client)]
    doomed = [k for k in plan_cloud_prune(keys, days) if k != key]
    for k in doomed:
        _cloud_call("حذف نسخه‌ی قدیمی", client.delete_object, Bucket=bucket, Key=k)
    return {"key": key, "size": size, "deleted": doomed}


def cloud_download(which, dest, *, client=None):
    """which = «latest» یا نام فایل (با یا بدون پیشوند database/). خروجی: مسیر فایل دانلودشده."""
    assert_cloud_ready()
    dest = Path(dest)
    if dest.exists():
        raise BackupError("فایل مقصد از قبل هست؛ مسیر دیگری بدهید.")
    client = client or build_client()
    keys = [k for k, _size in cloud_list(client)]
    if which == "latest":
        if not keys:
            raise BackupError("هیچ بکاپی در ابر نیست.")
        key = keys[0]
    else:
        key = which if which.startswith(PREFIX) else PREFIX + which
        if key not in keys:
            raise BackupError("چنین بکاپی در ابر نیست؛ با --list فهرست را ببین.")
    part = dest.with_name(dest.name + PART_SUFFIX)
    try:
        _cloud_call("دانلود", client.download_file, settings.BACKUP_CLOUD_BUCKET, key, str(part))
        os.replace(part, dest)
    finally:
        part.unlink(missing_ok=True)
    return dest


# ---------- اجرای کامل ----------
def run_backup(*, local_only=False, dest=None, say=print):
    dest = Path(dest or settings.BACKUP_DIR)
    try:
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        raise BackupError(f"پوشه‌ی بکاپ ({dest}) ساخته نشد؛ دسترسی را بررسی کنید.")
    with _Lock(dest):
        for stale in dest.glob(f"*{PART_SUFFIX}"):   # باقی‌مانده‌ی اجرای نیمه‌کاره؛ قفل دست ماست
            stale.unlink(missing_ok=True)
        path = dump_database(dest)
        say(f"dump ok: {path.name} ({_mb(path.stat().st_size)})")
        deleted = prune_local(dest, settings.BACKUP_LOCAL_KEEP_DAYS)
        say(f"local prune: {len(deleted)} old file(s) removed")
        if local_only:
            return {"path": path, "local_deleted": deleted, "cloud": None}
        try:
            cloud = cloud_upload(path)
        except BackupError as exc:
            raise BackupError(f"{exc} — بکاپ سرور سالم است: {path.name}") from exc
        say(f"cloud ok: {cloud['key']} ({_mb(cloud['size'])}); removed {len(cloud['deleted'])} old object(s)")
        return {"path": path, "local_deleted": deleted, "cloud": cloud}
