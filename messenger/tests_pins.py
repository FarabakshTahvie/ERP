from django.http import Http404
from django.urls import reverse

from messenger import services
from messenger.models import ChatState, Message
from messenger.tests import Base


class PinTests(Base):
    def test_any_member_pins_and_everyone_sees_it_newest_first(self):
        m1, m2 = self.send(self.t1, self.main, "اول"), self.send(self.t2, self.main, "دوم")
        services.set_pinned(self.t1, m1.pk, True)
        services.set_pinned(self.manager, m2.pk, True)
        for u in (self.t1, self.t2, self.acc):
            pins = services.fetch_messages(u, self.main)["pins"]
            self.assertEqual([p["id"] for p in pins], [m2.pk, m1.pk])
        services.set_pinned(self.t2, m2.pk, False)
        self.assertEqual([p["id"] for p in services.fetch_messages(self.t1, self.main)["pins"]], [m1.pk])

    def test_private_chat_pin_is_for_both_and_outsiders_get_404(self):
        conv = services.open_direct(self.t1, self.acc)
        m = self.send(self.t1, conv, "x")
        services.set_pinned(self.acc, m.pk, True)
        self.assertEqual(len(services.fetch_messages(self.t1, conv)["pins"]), 1)
        with self.assertRaises(Http404):
            services.set_pinned(self.t2, m.pk, True)
        r = self.login(self.t2).post(reverse("messenger:api_pin", args=[m.pk]), {"pinned": "1"})
        self.assertEqual(r.status_code, 404)

    def test_pin_limit_and_pinning_twice_is_harmless(self):
        ids = [self.send(self.t1, self.main, f"m{i}").pk for i in range(services.MAX_PINS + 1)]
        for pk in ids[:services.MAX_PINS]:
            services.set_pinned(self.t1, pk, True)
        services.set_pinned(self.t1, ids[0], True)
        with self.assertRaises(ValueError):
            services.set_pinned(self.t1, ids[-1], True)
        self.assertEqual(Message.objects.filter(pinned_at__isnull=False).count(), services.MAX_PINS)

    def test_deleted_message_is_unpinned_and_cannot_be_pinned(self):
        m = self.send(self.t1, self.main, "x")
        services.set_pinned(self.t1, m.pk, True)
        services.delete_message(self.t1, m.pk)
        m.refresh_from_db()
        self.assertIsNone(m.pinned_at)
        self.assertEqual(services.fetch_messages(self.t1, self.main)["pins"], [])
        with self.assertRaises(ValueError):
            services.set_pinned(self.t1, m.pk, True)

    def test_pin_does_not_look_like_an_edit(self):
        m = self.send(self.t1, self.main, "x")
        before = Message.objects.get(pk=m.pk).updated_at
        services.set_pinned(self.t2, m.pk, True)
        self.assertEqual(Message.objects.get(pk=m.pk).updated_at, before)

    def test_api_pin_roundtrip(self):
        m = self.send(self.t1, self.main, "سلام")
        c = self.login(self.t2)
        r = c.post(reverse("messenger:api_pin", args=[m.pk]), {"pinned": "1"}).json()
        self.assertEqual((r["ok"], [p["id"] for p in r["pins"]]), (True, [m.pk]))
        r = c.post(reverse("messenger:api_pin", args=[m.pk]), {"pinned": "0"}).json()
        self.assertEqual(r["pins"], [])


class UnreadMarkerTests(Base):
    def test_own_messages_never_count_even_if_read_marker_is_behind(self):
        self.send(self.t1, self.main, "من فرستادم")
        ChatState.objects.filter(conversation=self.main, user=self.t1).update(last_read_id=0)
        self.assertEqual(services.unread_total(self.t1), 0)
        main_item = next(i for i in services.inbox(self.t1)["items"] if i["key"] == "main")
        self.assertEqual(main_item["unread"], 0)


class PinPageTests(Base):
    def test_chat_page_layout_pin_bar_and_confirm_dialog(self):
        html = self.login(self.t1).get(reverse("messenger:chat", args=[self.main.pk])).content.decode("utf-8")
        start = html.index("data-msgr-form")
        form_end = html.index("</form>", start)
        form = html[start:form_end]
        self.assertLess(form.index('type="submit"'), form.index("<textarea"))   # ارسال اول = سمت راست در RTL
        self.assertNotIn("-scale-x-100", form)
        self.assertIn("data-msgr-pins", html)
        self.assertIn("data-pin-url=", html)
        self.assertGreater(html.index("data-msgr-confirm"), form_end)           # مودال بیرون از فرم
