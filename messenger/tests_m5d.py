from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

BASE = Path(settings.BASE_DIR)
CTL = "media-controller.msgr-player-video"
MODES = (":fullscreen", ":-webkit-full-screen")


def css():
    return (BASE / "static" / "src" / "input.css").read_text(encoding="utf-8")


def rule(selector):
    text = css()
    start = text.index(selector + " {")
    return text[start:text.index("}", start)]


class FullscreenVideoCssTests(SimpleTestCase):
    def test_fullscreen_controller_ignores_the_inline_bubble_aspect_ratio(self):
        for mode in MODES:
            r = rule(CTL + mode)
            self.assertIn("aspect-ratio: auto !important", r, mode)
            self.assertIn("--media-object-fit: contain", r, mode)
            self.assertIn("border-radius: 0", r, mode)

    def test_fullscreen_video_fills_the_screen_and_is_never_cropped(self):
        for mode in MODES:
            r = rule(CTL + mode + " video")
            for needle in ("position: absolute", "inset: 0", "width: 100%", "height: 100%",
                           "object-fit: contain", "max-height: none"):
                self.assertIn(needle, r, f"{mode}: {needle}")
            self.assertNotIn("cover", r, mode)

    def test_bubble_rules_outside_fullscreen_are_unchanged(self):
        text = css()
        self.assertIn("media-controller.msgr-player-video video { object-fit: contain; }", text)
        self.assertIn("aspect-ratio: 16 / 9;", rule(".chat-bubble media-controller.msgr-player.msgr-player-video"))
        self.assertNotIn("aspect-ratio: auto !important", rule(".chat-bubble media-controller.msgr-player.msgr-player-video"))
