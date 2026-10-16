from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from utils.image_utils import optimize_receipt_image
from utils.test_helpers import make_image_file
from finance.services import prepare_receipt_file


class ImageUtilsTests(TestCase):
    def test_invalid_image_bytes(self):
        # فایل با پسوند .jpg و بایت‌های ساختگی خطای «تصویر معتبری نیست» می‌دهد
        fake_file = SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg")
        with self.assertRaises(ValueError) as ctx:
            optimize_receipt_image(fake_file)
        self.assertIn("تصویر معتبری نیست", str(ctx.exception))

    def test_pdf_validation(self):
        # PDF بدون امضای %PDF- خطا می‌دهد و PDF واقعی بدون تغییر می‌ماند
        bad_pdf = SimpleUploadedFile("doc.pdf", b"fake content", content_type="application/pdf")
        with self.assertRaises(ValueError) as ctx:
            prepare_receipt_file(bad_pdf)
        self.assertIn("فایل PDF معتبر نیست", str(ctx.exception))

        good_pdf = SimpleUploadedFile("doc.pdf", b"%PDF-1.4 real valid header content", content_type="application/pdf")
        prepared = prepare_receipt_file(good_pdf)
        self.assertTrue(prepared.name.endswith(".pdf"))
        self.assertEqual(prepared.read()[:5], b"%PDF-")

    def test_randomized_filename(self):
        # نام فایل خروجی تصادفی است و شامل نام اصلی نیست
        named_file = make_image_file(name="sensitive_customer_bill.png", size=(100, 100), fmt="PNG")
        prepared = prepare_receipt_file(named_file)
        self.assertNotIn("sensitive_customer_bill", prepared.name)
