import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from messenger import media, services
from messenger.models import Attachment
from messenger.tests import Base


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


class SendWithFilesTests(MediaBase):
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

    def test_delete_message_removes_files(self):
        a = self.att(self.t1, self.main, self.doc())
        path = a.file.path
        msg = self.send_files(self.t1, self.main, [a])
        self.assertTrue(os.path.exists(path))
        services.delete_message(self.t1, msg.pk)
        self.assertFalse(os.path.exists(path))
        self.assertFalse(Attachment.objects.filter(pk=a.pk).exists())


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

    def test_unknown_types_are_downloads(self):
        a = self.att(self.t1, self.main, SimpleUploadedFile("page.html", b"<script>1</script>"))
        r = self.login(self.t1).get(self.url(a))
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])
