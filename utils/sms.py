import logging
import requests
from django.conf import settings
from notifications.sms_patterns import SMS_PATTERNS

logger = logging.getLogger(__name__)


class SMSService:
    BASE = "https://api.sms.ir/v1"

    def __init__(self):
        self.api_key = getattr(settings, "SMS_IR_API_KEY", "")
        self.line_number = getattr(settings, "SMS_IR_LINE_NUMBER", "")

    def _post(self, path, payload):
        if not self.api_key:
            return {"success": False, "error": "SMS_IR_API_KEY is empty"}
        try:
            r = requests.post(
                f"{self.BASE}/{path}", json=payload, timeout=10,
                headers={"X-API-KEY": self.api_key, "Accept": "application/json"},
            )
            data = r.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error("sms.ir request error: %s", e)
            return {"success": False, "error": str(e)}
        ok = r.status_code == 200 and data.get("status") == 1
        if not ok:
            logger.error("sms.ir failed: HTTP %s %s", r.status_code, str(data)[:300])  # هرگز کلید را لاگ نکن
        return {"success": ok, "data": data, "error": None if ok else (data.get("message") or f"HTTP {r.status_code}")}

    def send_pattern(self, mobile, pattern_key, **params):
        pattern = SMS_PATTERNS[pattern_key]
        missing = set(pattern["parameters"]) - set(params)
        if missing:
            raise ValueError(f"پارامتر ناقص برای {pattern_key}: {missing}")
        return self._post("send/verify", {
            "mobile": str(mobile),
            "templateId": int(pattern["pattern_code"]),
            "parameters": [{"name": p, "value": str(params[p])} for p in pattern["parameters"]],
        })

    def send_text(self, mobile, message):
        if not self.line_number:
            return {"success": False, "error": "SMS_IR_LINE_NUMBER is empty"}
        return self._post("send/bulk", {
            "lineNumber": int(self.line_number), "messageText": message, "mobiles": [str(mobile)],
        })

    def send_otp(self, mobile, code):
        return self.send_pattern(mobile, "login_otp", code=code)

    def send_invoice_issued(self, mobile, name, number, username, password, link):
        # link فقط «مسیر» است (مثل s/abc1234/)، چون دامنه در متن ثابت پترن هست
        return self.send_pattern(mobile, "invoice_issued_with_credentials",
                                 name=name, number=number, username=username, password=password, LINK=link)
