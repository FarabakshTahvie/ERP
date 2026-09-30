import re
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase, Client
from django.urls import reverse
from PIL import Image
from accounts.models import User


def _static_relpath(src):
    path = urlsplit(src).path
    prefix = "/" + settings.STATIC_URL.strip("/") + "/"
    assert path.startswith(prefix), src
    return path[len(prefix):]


class PwaManifestTests(TestCase):
    def _manifest(self):
        resp = Client().get(reverse("manifest"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("manifest+json", resp["Content-Type"])
        return resp.json()

    def test_manifest_is_public_and_declares_any_and_maskable_icons(self):
        data = self._manifest()
        declared = {(i["sizes"], i["purpose"]) for i in data["icons"]}
        self.assertIn(("192x192", "any"), declared)
        self.assertIn(("512x512", "any"), declared)
        self.assertIn(("512x512", "maskable"), declared)

    def test_manifest_background_matches_splash_css(self):
        data = self._manifest()
        css = (Path(settings.BASE_DIR) / "static" / "src" / "input.css").read_text(encoding="utf-8")
        block = re.search(r"\.fb-splash\s*\{[^}]*\}", css)
        self.assertIsNotNone(block)
        self.assertIn(data["background_color"].lower(), block.group(0).lower())

    def test_manifest_reachable_when_password_change_required(self):
        user = User.objects.create_user(username="pwa_mcp", phone_number="09190009001",
                                        password="Test@1234", must_change_password=True)
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get(reverse("manifest")).status_code, 200)


class PwaIconFilesTests(TestCase):
    def test_declared_icons_exist_and_sizes_are_real(self):
        data = Client().get(reverse("manifest")).json()
        for icon in data["icons"]:
            found = finders.find(_static_relpath(icon["src"]))
            self.assertIsNotNone(found, icon["src"])
            with Image.open(found) as img:
                self.assertEqual(img.format, "PNG")
                self.assertEqual(f"{img.width}x{img.height}", icon["sizes"], icon["src"])

    def test_maskable_and_apple_icons_are_opaque_white_background(self):
        for name, size in (("icon-maskable-512.png", (512, 512)), ("apple-touch-icon-180.png", (180, 180))):
            found = finders.find("icons/" + name)
            self.assertIsNotNone(found, name)
            with Image.open(found) as img:
                self.assertEqual(img.size, size)
                self.assertNotIn("A", img.mode, f"{name} نباید کانال شفافیت داشته باشد")
                self.assertEqual(img.convert("RGB").getpixel((0, 0)), (255, 255, 255))

    def test_animated_logo_file_exists(self):
        self.assertIsNotNone(finders.find("icons/logo-animated.svg"))


class PwaSplashMarkupTests(TestCase):
    def _login_html(self):
        return Client().get(reverse("accounts:login")).content.decode("utf-8")

    def test_splash_uses_data_src_not_src(self):
        html = self._login_html()
        self.assertIn('id="fb-splash"', html)
        self.assertRegex(html, r'data-src="[^"]*logo-animated\.svg')
        self.assertNotRegex(html, r'<img[^>]*\ssrc="[^"]*logo-animated')
        self.assertIn("fb_splash_seen", html)

    def test_splash_is_first_thing_in_body(self):
        html = self._login_html()
        self.assertLess(html.find('id="fb-splash"'), html.find("<main"))
