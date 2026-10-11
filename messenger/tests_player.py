import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from messenger.tests import Base

BASE = Path(settings.BASE_DIR)
VENDOR = BASE / "static" / "js" / "vendor" / "media-chrome.js"


def read(*parts):
    return BASE.joinpath(*parts).read_text(encoding="utf-8")


class PlayerVendorFileTests(SimpleTestCase):
    def test_vendor_bundle_is_a_single_file_iife(self):
        self.assertTrue(VENDOR.is_file())
        size = VENDOR.stat().st_size
        self.assertTrue(20_000 < size < 400_000, size)
        text = VENDOR.read_text(encoding="utf-8")
        self.assertIn("media-controller", text)
        self.assertIn("customElements", text)
        self.assertIsNone(re.search(r"(?m)^\s*(import|export)\s", text))
        self.assertIn("media-chrome", text[:300])

    def test_vendor_doc_exists(self):
        doc = read("docs", "vendor", "media-chrome.md")
        self.assertIn("MIT", doc)
        self.assertIn("esbuild", doc)


class PlayerPageTests(Base):
    def html(self, name, *args):
        return self.login(self.t1).get(reverse(name, args=args)).content.decode("utf-8")

    def test_chat_page_loads_vendor_before_media_script_from_own_domain(self):
        html = self.html("messenger:chat", self.main.pk)
        self.assertLess(html.index("js/vendor/media-chrome.js"), html.index("js/messenger_media.js"))
        for host in ("jsdelivr", "unpkg", "esm.sh", "cdnjs", "skypack"):
            self.assertNotIn(host, html)

    def test_light_pages_do_not_load_the_player_library(self):
        self.assertNotIn("media-chrome", self.html("messenger:inbox"))
        self.assertNotIn("media-chrome", self.html("messenger:tasks"))


class PlayerSourceTests(SimpleTestCase):
    def test_media_js_builds_players_with_native_fallback(self):
        js = read("static", "js", "messenger_media.js")
        for needle in ("customElements.get('media-controller')", "tag('media-controller'", "media-play-button",
                       "media-time-range", "media-fullscreen-button", "a.preload = 'metadata'",
                       "v.preload = 'metadata'", "a.controls = true", "v.controls = true"):
            self.assertIn(needle, js, needle)
        self.assertNotIn("preload = 'none'", js)

    def test_only_one_media_plays_at_a_time(self):
        js = read("static", "js", "messenger_media.js")
        self.assertIn("root.addEventListener('play'", js)
        self.assertIn(".pause()", js)

    def test_tapping_player_controls_does_not_open_message_menu(self):
        js = read("static", "js", "messenger_chat.js")
        self.assertIn("closest('a, button, video, audio, media-controller')", js)

    def test_player_css_is_in_input_css(self):
        css = read("static", "src", "input.css")
        for needle in ("media-controller.msgr-player", "msgr-player-video", "--media-primary-color"):
            self.assertIn(needle, css, needle)
