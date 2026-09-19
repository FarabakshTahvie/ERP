import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NajvaService:
    """
    نجوا به دو مقدار جدا نیاز داره: token (هدر Authorization) و api_key (بدنه‌ی درخواست).
    """
    BASE_URL = getattr(settings, "NAJVA_API_URL", "https://app.najva.com/api/v1/notifications/")

    def __init__(self):
        self.token = getattr(settings, "NAJVA_TOKEN", "")
        self.api_key = getattr(settings, "NAJVA_API_KEY", "")

    def send(self, title, body, subscriber_tokens, url=None, icon=None, image=None):
        if not subscriber_tokens:
            return {"success": False, "error": "no subscriber tokens"}
        payload = {"api_key": self.api_key, "title": title, "body": body, "subscriber_tokens": subscriber_tokens}
        if url:
            payload["url"] = url
        if icon:
            payload["icon"] = icon
        if image:
            payload["image"] = image
        try:
            response = requests.post(
                self.BASE_URL, json=payload,
                headers={"Authorization": f"Token {self.token}", "Content-Type": "application/json"},
                timeout=10,
            )
            return {
                "success": response.status_code in (200, 201, 202),
                "status_code": response.status_code,
                "data": response.json() if "application/json" in response.headers.get("content-type", "") else response.text,
            }
        except requests.exceptions.RequestException as e:
            logger.error("Najva push error: %s", e)
            return {"success": False, "error": str(e)}
