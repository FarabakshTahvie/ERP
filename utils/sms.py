from django.conf import settings
from notifications.sms_patterns import SMS_PATTERNS
from smsir.sms import UltraFastSend, send_by_mobile_number


class SMSService:
    def __init__(self):
        self.api_key = getattr(settings, 'SMS_IR_API_KEY', '')
        self.line_number = getattr(settings, 'SMS_IR_LINE_NUMBER', '')

    def send_pattern(self, mobile, pattern_key, **params):
        pattern = SMS_PATTERNS[pattern_key]
        missing = set(pattern["parameters"]) - set(params.keys())
        if missing:
            raise ValueError(f"پارامتر ناقص برای {pattern_key}: {missing}")
        parameter_array = [{"Name": p, "Value": str(params[p])} for p in pattern["parameters"]]
        try:
            return UltraFastSend(
                ParameterArray=parameter_array,
                Mobile=str(mobile),
                TemplateId=pattern["pattern_code"],
                Token=self.api_key
            )
        except Exception as e:
            return {"status": False, "message": str(e)}

    def send_otp(self, mobile, code):
        return self.send_pattern(mobile, "login_otp", code=code)

    def send_invoice_issued(self, mobile, name, number, username, password, link):
        return self.send_pattern(
            mobile,
            "invoice_issued_with_credentials",
            name=name,
            number=number,
            username=username,
            password=password,
            LINK=link
        )

    def send_text(self, mobile, message):
        try:
            return send_by_mobile_number(
                Messages=message,
                MobileNumbers=mobile,
                LineNumber=self.line_number,
                Token=self.api_key
            )
        except Exception as e:
            return {"status": False, "message": str(e)}
