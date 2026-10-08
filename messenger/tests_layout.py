import re

from django.urls import reverse

from messenger.tests import Base


class LayoutTests(Base):
    def page(self, url):
        html = self.login(self.t1).get(url).content.decode("utf-8")
        cls = re.search(r'<body[^>]*class="([^"]*)"', html).group(1).split()
        return cls, html

    def test_messenger_pages_lock_body_to_viewport_without_fixed_header_math(self):
        urls = (reverse("messenger:inbox"), reverse("messenger:chat", args=[self.main.pk]),
                reverse("messenger:tasks"))
        for url in urls:
            cls, html = self.page(url)
            self.assertIn("h-dvh", cls, url)
            self.assertIn("overflow-hidden", cls, url)
            self.assertNotIn("calc(100dvh", html, url)

    def test_other_pages_keep_normal_scrolling_body(self):
        cls, _ = self.page(reverse("accounts:change_password"))
        self.assertIn("min-h-full", cls)
        self.assertNotIn("h-dvh", cls)
        self.assertNotIn("overflow-hidden", cls)