import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

VERSION_KEY = "catalog:ver"
TTL = 600


def version():
    try:
        return cache.get(VERSION_KEY) or 1
    except Exception:
        logger.exception("catalog cache: version read failed")
        return 1


def bump():
    """نسخه‌ی ویترین را بالا می‌برد؛ همه‌ی کلیدهای قبلی بی‌اثر می‌شوند."""
    try:
        try:
            cache.incr(VERSION_KEY)
        except ValueError:
            cache.set(VERSION_KEY, 2, None)
    except Exception:
        logger.exception("catalog cache: bump failed")


def remember(key, build, ttl=TTL):
    """build() فقط وقتی اجرا می‌شود که کش خالی است. هر خطای ردیس فقط لاگ می‌شود و صفحه بدون کش کار می‌کند."""
    full = f"catalog:{version()}:{key}"
    try:
        hit = cache.get(full)
        if hit is not None:
            return hit
    except Exception:
        logger.exception("catalog cache: get failed")
    value = build()
    try:
        cache.set(full, value, ttl)
    except Exception:
        logger.exception("catalog cache: set failed")
    return value
