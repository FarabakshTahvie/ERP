from django.test import TestCase

from accounts.models import OTPCode


class OTPCodeTests(TestCase):
    def test_generate_and_verify(self):
        phone = "09121112233"
        otp, code = OTPCode.generate(phone, OTPCode.Purpose.LOGIN)
        self.assertIsNotNone(otp)
        self.assertEqual(len(code), 5)
        self.assertFalse(otp.is_used)

        # اشتباه
        ok, msg = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, "99999")
        self.assertFalse(ok)

        # درست
        ok, verified_otp = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, code)
        self.assertTrue(ok)
        self.assertTrue(verified_otp.is_used)

    def test_expired_otp(self):
        phone = "09129998877"
        otp, code = OTPCode.generate(phone, OTPCode.Purpose.LOGIN, ttl_minutes=-5)
        ok, msg = OTPCode.verify(phone, OTPCode.Purpose.LOGIN, code)
        self.assertFalse(ok)
        self.assertIn("منقضی", msg)
