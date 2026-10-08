import uuid
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.test import Client
from django.urls import resolve, reverse

from messenger import services
from messenger.tests import Base

ICONS = ("message-circle", "reply", "check-check", "bell-off", "arrow-down", "send", "x", "check", "pencil",
         "trash-2", "copy", "users", "search", "bell", "clock", "refresh-cw", "arrow-right")


class PageTests(Base):
    def test_page_access_matrix(self):
        conv = services.open_direct(self.t1, self.acc)
        for name, args in (("messenger:inbox", []), ("messenger:chat", [self.main.pk])):
            url = reverse(name, args=args)
            for user, code in ((self.manager, 200), (self.acc, 200), (self.t1, 200), (self.cli, 404)):
                self.assertEqual(self.login(user).get(url).status_code, code, f"{name} {user.username}")
            self.assertEqual(Client().get(url).status_code, 302)
        private = reverse("messenger:chat", args=[conv.pk])
        self.assertEqual(self.login(self.acc).get(private).status_code, 200)
        for outsider in (self.t2, self.manager, self.cli):
            self.assertEqual(self.login(outsider).get(private).status_code, 404, outsider.username)

    def test_initial_json_is_escaped_not_raw_html(self):
        self.send(self.t1, self.main, "<script>alert(1)</script>")
        html = self.login(self.t2).get(reverse("messenger:chat", args=[self.main.pk])).content.decode("utf-8")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("\\u003Cscript\\u003Ealert(1)\\u003C/script\\u003E", html)

    def test_chat_page_has_no_footer_and_has_form(self):
        html = self.login(self.t1).get(reverse("messenger:chat", args=[self.main.pk])).content.decode("utf-8")
        self.assertNotIn("پشتیبانی:", html)
        self.assertIn("data-msgr-form", html)
        self.assertIn('maxlength="4000"', html)

    def test_serialize_exposes_uid_only_to_sender(self):
        uid = str(uuid.uuid4())
        msg, _ = services.send_message(self.t1, self.main, text="x", client_uid=uid)
        self.assertEqual(services.serialize_message(msg, self.t1)["uid"], uid)
        self.assertEqual(services.serialize_message(msg, self.t2)["uid"], "")

    def test_unread_total_matches_inbox(self):
        conv = services.open_direct(self.t1, self.acc)
        self.send(self.t1, conv, "a")
        self.send(self.t1, conv, "b")
        self.send(self.manager, self.main, "g")
        services.set_muted(self.acc, self.main, True)
        for u in (self.acc, self.t1, self.manager, self.t2):
            self.assertEqual(services.unread_total(u), services.inbox(u)["total_unread"], u.username)
        self.assertEqual(services.unread_total(self.acc), 2)

    def test_chat_meta(self):
        conv = services.open_direct(self.t1, self.acc)
        meta = services.chat_meta(self.t1, conv)
        self.assertEqual((meta["key"], meta["title"], meta["is_main"]), (f"u{self.acc.pk}", "ms_acc", False))
        main = services.chat_meta(self.t1, self.main)
        self.assertEqual((main["key"], main["title"], main["members"]), ("main", "فراگرام", 4))

    def test_push_link_resolves_to_chat_page(self):
        msg = self.send(self.t1, self.main, "x")
        self.assertEqual(resolve(urlsplit(services.push_url(msg)).path).view_name, "messenger:chat")

    def test_header_badge_only_for_staff(self):
        self.send(self.manager, self.main, "hi")
        html = self.login(self.t1).get(reverse("accounts:change_password")).content.decode("utf-8")
        self.assertRegex(html, r"data-msgr-badge[^>]*>\s*۱\s*<")
        client_html = self.login(self.cli).get(reverse("home")).content.decode("utf-8")
        self.assertNotIn("data-msgr-badge", client_html)

    def test_static_assets_are_registered_and_icons_exist(self):
        base = Path(settings.BASE_DIR)
        css = (base / "static" / "src" / "input.css").read_text(encoding="utf-8")
        for name in ("messenger_common", "messenger_inbox", "messenger_chat"):
            self.assertTrue((base / "static" / "js" / f"{name}.js").is_file(), name)
            self.assertIn(f'@source "../js/{name}.js";', css)
        sprite = (base / "static" / "icons" / "sprite.svg").read_text(encoding="utf-8")
        for icon in ICONS:
            self.assertRegex(sprite, rf'id=["\']{icon}["\']', icon)
