from io import BytesIO
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from utils.image_utils import optimize_receipt_image, optimize_image
from utils.test_helpers import make_image_file
from finance.services import prepare_receipt_file


class ImageUtilsTests(TestCase):
    def test_jpeg_resize_and_webp(self):
        # تصویر JPEG با ابعاد ۳۰۰۰×۱۵۰۰ به ۲۴۰۰×۱۲۰۰ و فرمت WebP تبدیل می‌شود
        jpeg_file = make_image_file(name="big.jpg", size=(3000, 1500), fmt="JPEG")
        optimized, changed = optimize_receipt_image(jpeg_file)
        self.assertTrue(changed)
        img = Image.open(optimized)
        self.assertEqual(img.format, "WEBP")
        self.assertEqual(img.size, (2400, 1200))

    def test_small_image_never_grows(self):
        # تصویر کوچک هرگز بزرگ‌تر از اصل نمی‌شود
        small_file = make_image_file(name="small.png", size=(40, 30), fmt="PNG")
        original_size = small_file.size
        optimized, _ = optimize_receipt_image(small_file)
        self.assertLessEqual(optimized.size, original_size)

    def test_exif_orientation_transposition(self):
        # EXIF با جهت ۶ روی تصویر ۲۰۰×۱۰۰ خروجی ۱۰۰×۲۰۰ می‌دهد
        oriented = make_image_file(name="oriented.jpg", size=(200, 100), fmt="JPEG", exif_orientation=6)
        optimized, _ = optimize_receipt_image(oriented)
        img = Image.open(optimized)
        self.assertEqual(img.size, (100, 200))

    def test_transparent_png_white_background(self):
        # PNG شفاف روی زمینه‌ی سفید می‌نشیند
        rgba_img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 0))  # قرمز کاملاً شفاف
        buffer = BytesIO()
        rgba_img.save(buffer, format="PNG")
        uploaded = SimpleUploadedFile("transparent.png", buffer.getvalue(), content_type="image/png")

        optimized, _ = optimize_receipt_image(uploaded)
        img = Image.open(optimized)
        # پیکسل باید سفید (255, 255, 255) باشد نه سیاه
        pixel = img.getpixel((50, 50))
        self.assertEqual(pixel, (255, 255, 255))

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

    def test_avatar_exif_transposition(self):
        # optimize_image آواتار با EXIF جهت‌دار درست چرخیده ذخیره می‌شود
        oriented = make_image_file(name="avatar.jpg", size=(400, 200), fmt="JPEG", exif_orientation=6)
        optimized = optimize_image(oriented, profile_name="avatar")
        img = Image.open(optimized)
        self.assertEqual(img.size, (200, 200))
