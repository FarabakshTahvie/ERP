from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from PIL import Image

from messenger import media, services
from messenger.models import Attachment
from messenger.tests_media import MediaBase
from utils.test_helpers import make_image_file

BASE = Path(settings.BASE_DIR)


def read(*parts):
    return BASE.joinpath(*parts).read_text(encoding="utf-8")


class VideoPosterTests(MediaBase):
    def upload(self, user, conv, **data):
        return self.login(user).post(reverse("messenger:api_upload", args=[conv.pk]), data).json()

    def video(self, name="v.mp4"):
        return SimpleUploadedFile(name, b"x" * 50)

    def test_poster_and_size_are_kept_as_small_webp(self):
        r = self.upload(self.t1, self.main, file=self.video(), width="1280", height="720",
                        poster=make_image_file("p.jpg", size=(1200, 700), fmt="JPEG"))
        a = r["attachment"]
        self.assertEqual((r["ok"], a["kind"], a["w"], a["h"], a["peaks"]), (True, "video", 1280, 720, []))
        self.assertTrue(a["thumb"])
        with Image.open(Attachment.objects.get(pk=a["id"]).thumb.path) as im:
            self.assertEqual(im.format, "WEBP")
            self.assertLessEqual(max(im.size), media.THUMB_SIDE)

    def test_bad_poster_and_bad_size_are_ignored_without_blocking_the_video(self):
        r = self.upload(self.t1, self.main, file=self.video(), width="abc", height="720",
                        poster=SimpleUploadedFile("p.jpg", b"not an image"))
        a = r["attachment"]
        self.assertEqual((r["ok"], a["thumb"], a["w"], a["h"]), (True, "", None, None))
        r = self.upload(self.t1, self.main, file=self.video("v2.mp4"), width="99999", height="720")
        self.assertEqual((r["attachment"]["w"], r["attachment"]["h"]), (None, None))

    def test_oversized_poster_is_ignored(self):
        p = make_image_file("p.jpg", size=(300, 200), fmt="JPEG")
        p.size = media.MAX_POSTER_BYTES + 1
        self.assertFalse(media.save_upload(self.t1, self.main, self.video(), poster=p).thumb)

    def test_poster_is_only_for_videos(self):
        att = media.save_upload(self.t1, self.main, self.doc(), width=100, height=100,
                                poster=make_image_file("p.jpg", size=(300, 200), fmt="JPEG"))
        self.assertEqual((bool(att.thumb), att.width, att.height), (False, None, None))

    def test_poster_follows_the_same_access_rules_as_the_file(self):
        conv = services.open_direct(self.t1, self.acc)
        a = media.save_upload(self.t1, conv, self.video(),
                              poster=make_image_file("p.jpg", size=(600, 400), fmt="JPEG"))
        thumb = media.serialize_attachment(a)["thumb"]
        self.assertEqual(self.login(self.t1).get(thumb).status_code, 200)
        self.assertEqual(self.login(self.acc).get(thumb).status_code, 404)    # هنوز یتیم
        self.send_files(self.t1, conv, [a])
        self.assertEqual(self.login(self.acc).get(thumb).status_code, 200)
        for outsider in (self.t2, self.manager, self.cli):
            self.assertEqual(self.login(outsider).get(thumb).status_code, 404, outsider.username)


class WaveformPeaksTests(MediaBase):
    def upload(self, **data):
        return self.login(self.t1).post(reverse("messenger:api_upload", args=[self.main.pk]), data).json()

    def test_valid_peaks_are_stored_and_returned(self):
        peaks = ",".join(str(i * 3) for i in range(32))
        a = self.upload(file=SimpleUploadedFile("v.webm", b"x" * 50), voice="1", duration="5", peaks=peaks)["attachment"]
        self.assertEqual((a["kind"], len(a["peaks"]), a["peaks"][:3]), ("voice", 32, [0, 3, 6]))
        self.assertEqual(len(Attachment.objects.get(pk=a["id"]).peaks), 32)

    def test_bad_peaks_are_ignored(self):
        bad = ["", "a,b,c", "1,2,3", ",".join(["50"] * 65), ",".join(["101"] * 20), ",".join(["-1"] * 20)]
        for raw in bad:
            a = self.upload(file=SimpleUploadedFile("a.mp3", b"x" * 50), peaks=raw)["attachment"]
            self.assertEqual(a["peaks"], [], raw)
            self.assertIsNone(Attachment.objects.get(pk=a["id"]).peaks, raw)

    def test_peaks_are_only_for_audio_kinds(self):
        raw = ",".join(["10"] * 20)
        self.assertIsNone(media.save_upload(self.t1, self.main, self.doc(), peaks=raw).peaks)
        self.assertEqual(len(media.save_upload(self.t1, self.main, SimpleUploadedFile("a.mp3", b"x"), peaks=raw).peaks), 20)


class PlayerPolishSourceTests(SimpleTestCase):
    def test_times_are_shown_with_persian_digits(self):
        js = read("static", "js", "messenger_media.js")
        for needle in ("function persianDigits(", "createTreeWalker", "new MutationObserver",
                       "faTag('media-time-display'", "faTag('media-duration-display'"):
            self.assertIn(needle, js, needle)

    def test_video_uses_poster_and_real_aspect_ratio(self):
        js = read("static", "js", "messenger_media.js")
        for needle in ("v.poster = f.thumb", "style.aspectRatio", "function videoPoster(",
                       "fd.append('poster'", "fd.append('width'", "fd.append('height'"):
            self.assertIn(needle, js, needle)

    def test_waveform_is_built_and_seeks_the_audio_element(self):
        js = read("static", "js", "messenger_media.js")
        for needle in ("function audioPeaks(", "OfflineAudioContext", "fd.append('peaks'", "function waveSeek(",
                       "setAttribute('role', 'slider')", "a.currentTime = ", "'pointerdown'", "f.peaks"):
            self.assertIn(needle, js, needle)

    def test_audio_background_is_transparent_and_wave_styles_exist(self):
        css = read("static", "src", "input.css")
        for needle in ("--media-background-color: transparent", ".msgr-wave {", ".msgr-wave-bar {",
                       ".msgr-wave-on", "--media-control-padding: 0 6px",
                       "media-controller.msgr-player-video[mediaisfullscreen]", "aspect-ratio: auto !important"):
            self.assertIn(needle, css, needle)
