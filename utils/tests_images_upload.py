import tempfile
import shutil
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from utils.image_utils import optimize_upload, optimize_named
from utils.test_helpers import make_image_file


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImageOptimizeBehaviorTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_big_image_optimized(self):
        img = make_image_file("big.jpg", size=(3000, 2000), fmt="JPEG")
        res_file, changed = optimize_upload(img)
        self.assertTrue(changed)

    def test_small_webp_untouched(self):
        img = make_image_file("small.webp", size=(100, 100), fmt="WEBP")
        res_file, changed = optimize_upload(img)
        self.assertFalse(changed)

    def test_corrupted_image_raises_value_error(self):
        fake = SimpleUploadedFile("fake.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIFbadbytes", content_type="image/jpeg")
        with self.assertRaises(ValueError):
            optimize_upload(fake)

    def test_optimize_named(self):
        img = make_image_file("pic.jpg", size=(1000, 1000), fmt="JPEG")
        f, name = optimize_named(img, "my photo.jpg")
        self.assertEqual(name, "my photo.webp")

        pdf = SimpleUploadedFile("doc.pdf", b"%PDF test", content_type="application/pdf")
        f2, name2 = optimize_named(pdf, "doc.pdf")
        self.assertEqual(name2, "doc.pdf")
