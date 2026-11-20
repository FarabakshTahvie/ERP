import functools
import logging

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class StorageError(ValueError):
    """خطای فضای ابری؛ پیامش فارسی و قابل نمایش به کاربر است."""


class ObjectMissing(StorageError):
    pass


class RangeNotSatisfiable(StorageError):
    pass


def configured():
    return bool(settings.ARVAN_FILES_ACCESS_KEY and settings.ARVAN_FILES_SECRET_KEY
                and settings.ARVAN_FILES_BUCKET and settings.ARVAN_FILES_ENDPOINT)


def build_client(*, addressing=None, signature=None):
    import boto3
    from botocore.config import Config
    cfg = Config(
        signature_version=signature or settings.ARVAN_FILES_SIGNATURE,
        s3={"addressing_style": addressing or settings.ARVAN_FILES_ADDRESSING_STYLE},
        connect_timeout=5, read_timeout=30, retries={"max_attempts": 2},
        # botocore جدید پیش‌فرض چک‌سام CRC32 می‌فرستد و بعضی S3های سازگار آن را رد می‌کنند
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )
    return boto3.client(
        "s3", endpoint_url=settings.ARVAN_FILES_ENDPOINT,
        aws_access_key_id=settings.ARVAN_FILES_ACCESS_KEY,
        aws_secret_access_key=settings.ARVAN_FILES_SECRET_KEY,
        region_name=settings.ARVAN_FILES_REGION or None, config=cfg)


@functools.lru_cache(maxsize=1)
def _client():
    return build_client()


def _need_client():
    if not configured():
        raise StorageError("فضای ابری تنظیم نشده است؛ با مدیر سیستم تماس بگیرید.")
    return _client()


def _info(exc):
    if isinstance(exc, ClientError):
        return (exc.response.get("Error", {}).get("Code", ""),
                exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode"))
    return type(exc).__name__, None


def _fail(exc, action):
    code, status = _info(exc)
    logger.error("arvan %s failed: http=%s code=%s", action, status, code)   # فقط کد؛ بدون کلید
    raise StorageError("ارتباط با فضای ابری برقرار نشد؛ کمی بعد دوباره تلاش کنید.") from exc


def put(key, uploaded):
    client = _need_client()
    try:
        uploaded.seek(0)
        client.put_object(Bucket=settings.ARVAN_FILES_BUCKET, Key=key, Body=uploaded.file,
                          ContentType="application/octet-stream")
    except (ClientError, BotoCoreError) as exc:
        _fail(exc, "put")


def delete(key):
    client = _need_client()
    try:
        client.delete_object(Bucket=settings.ARVAN_FILES_BUCKET, Key=key)   # کلید ناموجود هم موفق است
    except (ClientError, BotoCoreError) as exc:
        _fail(exc, "delete")


def open_object(key, byte_range=None):
    """پاسخ get_object (Body، ContentLength، ContentRange)."""
    client = _need_client()
    kwargs = {"Bucket": settings.ARVAN_FILES_BUCKET, "Key": key}
    if byte_range:
        kwargs["Range"] = byte_range
    try:
        return client.get_object(**kwargs)
    except (ClientError, BotoCoreError) as exc:
        code, status = _info(exc)
        if code in ("NoSuchKey", "404") or status == 404:
            raise ObjectMissing("فایل در فضای ابری پیدا نشد.") from exc
        if code == "InvalidRange" or status == 416:
            raise RangeNotSatisfiable("بازه‌ی درخواستی نامعتبر است.") from exc
        _fail(exc, "get")
