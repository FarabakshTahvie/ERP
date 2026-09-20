import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

ERROR_HINTS = {
    400: "پارامتر ورودی نامعتبر است",
    403: "API Key نجوا نامعتبر است",
    414: "بیش از ۱۰۰۰ توکن در یک درخواست",
    415: "حجم فایل غیرمجاز",
    416: "IP این سرور در پنل نجوا وایت‌لیست نشده",
    418: "اعتبار نجوا برای ارسال کافی نیست",
}


class NajvaService:
    MAX_TOKENS = 1000
    SENDER_URL = "https://push.najva.com/v1/sender"

    def __init__(self):
        self.api_key = getattr(settings, "NAJVA_API_KEY", "")
        self.website_id = getattr(settings, "NAJVA_WEBSITE_ID", "")
        self.url = getattr(settings, "NAJVA_SEND_URL", "https://push.najva.com/v1/send/token/")

    @property
    def configured(self):
        return bool(self.api_key and self.website_id)

    def send(self, title, body, subscriber_tokens, url=None, ttl=24):
        tokens = list(subscriber_tokens or [])[: self.MAX_TOKENS]
        if not tokens:
            return {"success": False, "error": "no subscriber tokens", "invalid_tokens": []}
        if not self.configured:
            logger.warning("Najva not configured; push skipped")
            return {"success": False, "error": "najva not configured", "invalid_tokens": []}

        click_url = url if (url and url.startswith("https://")) else settings.SITE_BASE_URL
        fields = [
            ("website_id", self.website_id),
            ("ttl", ttl),
            ("message.title", title[:250]),
            ("message.body", body[:400]),
            ("message.notification_click.click_url", click_url[:250]),
        ] + [("tokens[]", t) for t in tokens]
        files = [(k, (None, str(v))) for k, v in fields]  # multipart واقعی؛ Content-Type را دستی نگذار

        try:
            resp = requests.post(self.url, files=files, headers={"apiKey": self.api_key}, timeout=10)
        except requests.exceptions.RequestException as e:
            logger.error("Najva request error: %s", e)
            return {"success": False, "error": str(e), "invalid_tokens": []}

        if resp.status_code not in (200, 201, 202):
            hint = ERROR_HINTS.get(resp.status_code, resp.text[:300])
            logger.error("Najva HTTP %s: %s", resp.status_code, hint)
            return {"success": False, "status_code": resp.status_code, "error": hint, "invalid_tokens": []}

        try:
            data = resp.json()
        except ValueError:
            data = {}
        entries = data.get("Entries") or {}
        results = entries.get("tokens", [])
        return {
            "success": any(r.get("status") in ("Sent", "Scheduled") for r in results),
            "request_id": entries.get("request_id"),
            "invalid_tokens": [r["token"] for r in results if r.get("status") == "InvalidToken"],
            "data": data,
        }

    def list_websites(self):
        """برای دستور najva_check: گرفتن website_id و آدرس سایت‌های ثبت‌شده."""
        try:
            r = requests.get(self.SENDER_URL, headers={"apiKey": self.api_key}, timeout=10)
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
        if r.status_code != 200:
            return {"success": False, "status_code": r.status_code, "error": ERROR_HINTS.get(r.status_code, r.text[:300])}
        return {"success": True, "websites": (r.json().get("Entries") or {}).get("websites", [])}
