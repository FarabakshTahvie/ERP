from django.test import Client
from django.urls import reverse

from messenger import services
from messenger.tests import Base


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


class ViewportHeightTests(Base):
    GOOD = "h-[var(--fb-app-h,100dvh)]"
    BAD = "h-dvh"

    def test_messenger_pages_use_the_measured_height(self):
        pages = (reverse("messenger:inbox"), reverse("messenger:chat", args=[self.main.pk]),
                 reverse("messenger:tasks"))
        for url in pages:
            html = self.login(self.t1).get(url).content.decode("utf-8")
            self.assertIn(self.GOOD, html, url)
            self.assertNotIn(self.BAD, html, url)

    def test_base_measures_real_height_and_follows_the_keyboard(self):
        html = self.login(self.t1).get(reverse("messenger:inbox")).content.decode("utf-8")
        self.assertIn("--fb-app-h", html)
        self.assertIn("window.innerHeight", html)
        self.assertIn("interactive-widget=resizes-content", html)

