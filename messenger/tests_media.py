import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from messenger import media, services
from messenger.models import Attachment
from messenger.tests import Base
from utils.test_helpers import make_image_file

ICONS = ("paperclip", "mic", "play", "pause", "square", "download", "file-text", "image")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MediaBase(Base):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def doc(self, name="a.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 x")

    def att(self, user, conv, f, **kw):
        return media.save_upload(user, conv, f, **kw)

    def send_files(self, user, conv, atts, text=""):
        return services.send_message(user, conv, text=text, attachment_ids=[a.pk for a in atts])[0]


class UploadTests(MediaBase):
    def test_kinds_and_orphan_state(self):
        c = self.login(self.t1)
        url = reverse("messenger:api_upload", args=[self.main.pk])
        img = c.post(url, {"file": make_image_file("p.png", size=(80, 60))}).json()["attachment"]
        pdf = c.post(url, {"file": self.doc()}).json()["attachment"]
        vid = c.post(url, {"file": SimpleUploadedFile("v.mp4", b"x" * 50)}).json()["attachment"]
        voice = c.post(url, {"file": SimpleUploadedFile("v.webm", b"x" * 50), "voice": "1", "duration": "7"}).json()["attachment"]
        self.assertEqual((img["kind"], pdf["kind"], vid["kind"], voice["kind"]), ("image", "file", "video", "voice"))
        self.assertEqual((voice["dur"], img["w"], img["h"]), (7, 80, 60))
        self.assertFalse(Attachment.objects.filter(message__isnull=False).exists())

    def test_access_rules(self):
        conv = services.open_direct(self.t1, self.acc)
        url = reverse("messenger:api_upload", args=[conv.pk])
        self.assertEqual(self.login(self.t2).post(url, {"file": self.doc()}).status_code, 404)
        self.assertEqual(self.login(self.cli).post(url, {"file": self.doc()}).status_code, 404)
        self.assertEqual(self.login(self.acc).post(url, {"file": self.doc()}).status_code, 200)

    def test_size_limit_and_fake_image(self):
        f = self.doc()
        f.size = media.MAX_BYTES + 1
        with self.assertRaises(ValueError):
            self.att(self.t1, self.main, f)
        bad = self.login(self.t1).post(reverse("messenger:api_upload", args=[self.main.pk]),
                                       {"file": SimpleUploadedFile("x.jpg", b"not an image")})
        self.assertEqual((bad.status_code, bad.json()["ok"]), (400, False))

    def test_big_image_is_optimized_and_gets_thumbnail(self):
        a = self.att(self.t1, self.main, make_image_file("big.jpg", size=(3000, 2000), fmt="JPEG"))
        self.assertEqual((a.width, a.height), (2400, 1600))
        self.assertTrue(a.thumb)
        with Image.open(a.thumb.path) as t:
            self.assertLessEqual(max(t.size), media.THUMB_SIDE)
        small = self.att(self.t1, self.main, make_image_file("s.png", size=(80, 60)))
        self.assertFalse(small.thumb)

    def test_old_orphans_are_cleaned_on_next_upload(self):
        old = self.att(self.t1, self.main, self.doc())
        Attachment.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=25))
        self.att(self.t1, self.main, self.doc("b.pdf"))
        self.assertFalse(Attachment.objects.filter(pk=old.pk).exists())


class SendWithFilesTests(MediaBase):
    def test_album_keeps_order_and_empty_text_is_ok(self):
        a, b, c = (self.att(self.t1, self.main, make_image_file(f"{i}.png", size=(50, 50))) for i in range(3))
        msg = self.send_files(self.t1, self.main, [c, a, b])
        files = services.fetch_messages(self.t2, self.main)["messages"][-1]["files"]
        self.assertEqual([f["id"] for f in files], [c.pk, a.pk, b.pk])
        self.assertEqual(msg.text, "")
        self.assertEqual(Attachment.objects.filter(message=msg).count(), 3)

    def test_attach_rules(self):
        mine = self.att(self.t1, self.main, self.doc())
        theirs = self.att(self.t2, self.main, self.doc("t.pdf"))
        with self.assertRaises(ValueError):
            self.send_files(self.t1, self.main, [theirs])           # آپلود دیگری
        voice = self.att(self.t1, self.main, SimpleUploadedFile("v.webm", b"x"), voice=True, duration=3)
        with self.assertRaises(ValueError):
            self.send_files(self.t1, self.main, [voice, mine])      # صدا با فایل دیگر
        with self.assertRaises(ValueError):
            services.send_message(self.t1, self.main, text="x", attachment_ids=list(range(1000, 1011)))  # بیش از ۱۰
        self.send_files(self.t1, self.main, [mine])
        with self.assertRaises(ValueError):
            services.send_message(self.t1, self.main, text="x", attachment_ids=[mine.pk])               # استفاده‌ی دوباره

    def test_send_with_files_is_idempotent(self):
        a = self.att(self.t1, self.main, self.doc())
        uid = "9b2f8d6e-5c1a-4f3e-8a7b-1c2d3e4f5a6b"
        m1, c1 = services.send_message(self.t1, self.main, text="", client_uid=uid, attachment_ids=[a.pk])
        m2, c2 = services.send_message(self.t1, self.main, text="", client_uid=uid, attachment_ids=[a.pk])
        self.assertEqual((m1.pk, c1, c2), (m2.pk, True, False))

    def test_delete_message_removes_files(self):
        a = self.att(self.t1, self.main, self.doc())
        path = a.file.path
        msg = self.send_files(self.t1, self.main, [a])
        self.assertTrue(os.path.exists(path))
        services.delete_message(self.t1, msg.pk)
        self.assertFalse(os.path.exists(path))
        self.assertFalse(Attachment.objects.filter(pk=a.pk).exists())

    def test_snippets_and_push_text_for_media_only_messages(self):
        a = self.att(self.t1, self.main, make_image_file("a.png", size=(50, 50)))
        msg = self.send_files(self.t1, self.main, [a])
        self.assertEqual(services.push_payload(msg)[1], "عکس")
        item = next(i for i in services.inbox(self.t2)["items"] if i["key"] == "main")
        self.assertEqual(item["last"]["text"], "عکس")
        reply = services.send_message(self.t2, self.main, text="باشه", reply_to_id=msg.pk)[0]
        self.assertEqual(services.fetch_messages(self.t1, self.main)["messages"][-1]["reply"]["snippet"], "عکس")
        self.assertEqual(reply.reply_to_id, msg.pk)


class ServingTests(MediaBase):
    def url(self, att):
        return media.serialize_attachment(att)["url"]

    def test_orphan_only_for_uploader_then_conversation_members(self):
        conv = services.open_direct(self.t1, self.acc)
        a = self.att(self.t1, conv, self.doc())
        url = self.url(a)
        self.assertEqual(self.login(self.t1).get(url).status_code, 200)
        self.assertEqual(self.login(self.acc).get(url).status_code, 404)    # هنوز یتیم
        self.send_files(self.t1, conv, [a])
        self.assertEqual(self.login(self.acc).get(url).status_code, 200)
        for outsider in (self.t2, self.manager, self.cli):
            self.assertEqual(self.login(outsider).get(url).status_code, 404, outsider.username)

    def test_thumbnail_follows_the_same_rules(self):
        conv = services.open_direct(self.t1, self.acc)
        a = self.att(self.t1, conv, make_image_file("big.jpg", size=(1200, 900), fmt="JPEG"))
        self.send_files(self.t1, conv, [a])
        thumb = media.serialize_attachment(a)["thumb"]
        self.assertEqual(self.login(self.acc).get(thumb).status_code, 200)
        self.assertEqual(self.login(self.t2).get(thumb).status_code, 404)

    def test_range_requests_and_inline_audio(self):
        a = self.att(self.t1, self.main, SimpleUploadedFile("a.mp3", b"0123456789"))
        c = self.login(self.t1)
        r = c.get(self.url(a), HTTP_RANGE="bytes=2-5")
        self.assertEqual((r.status_code, b"".join(r.streaming_content), r["Content-Range"]), (206, b"2345", "bytes 2-5/10"))
        r = c.get(self.url(a), HTTP_RANGE="bytes=-3")
        self.assertEqual((r.status_code, b"".join(r.streaming_content)), (206, b"789"))
        self.assertEqual(c.get(self.url(a), HTTP_RANGE="bytes=50-").status_code, 416)
        full = c.get(self.url(a))
        self.assertEqual((full.status_code, full["Accept-Ranges"], full["Content-Type"]), (200, "bytes", "audio/mpeg"))
        self.assertNotIn("attachment", full["Content-Disposition"])
        self.assertEqual(b"".join(full.streaming_content), b"0123456789")

    def test_unknown_types_are_downloads(self):
        a = self.att(self.t1, self.main, SimpleUploadedFile("page.html", b"<script>1</script>"))
        r = self.login(self.t1).get(self.url(a))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])


class MediaPageTests(MediaBase):
    def test_chat_page_composer_layout_and_viewer(self):
        html = self.login(self.t1).get(reverse("messenger:chat", args=[self.main.pk])).content.decode("utf-8")
        start = html.index("data-msgr-form")
        form = html[start:html.index("</form>", start)]
        order = [form.index('type="submit"'), form.index("data-msgr-clip"), form.index("<textarea"), form.index("data-msgr-mic")]
        self.assertEqual(order, sorted(order))                    # راست به چپ: ارسال، گیره، ورودی، میکروفون
        self.assertIn("data-upload-url=", html)
        self.assertIn("data-msgr-tray", html)
        self.assertGreater(html.index("data-msgr-viewer"), html.index("</form>", start))

    def test_media_js_registered_and_icons_exist(self):
        base = Path(settings.BASE_DIR)
        self.assertTrue((base / "static" / "js" / "messenger_media.js").is_file())
        css = (base / "static" / "src" / "input.css").read_text(encoding="utf-8")
        self.assertIn('@source "../js/messenger_media.js";', css)
        sprite = (base / "static" / "icons" / "sprite.svg").read_text(encoding="utf-8")
        for icon in ICONS:
            self.assertRegex(sprite, rf'id=["\']{icon}["\']', icon)
