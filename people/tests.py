from datetime import datetime, time, timedelta
from decimal import Decimal

import jdatetime
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginHistory, User, UserPresence
from catalog.models import Item
from core.models import Party, Specialty
from finance import accounting
from finance.models import Invoice, Payment
from inventory.models import Warehouse
from inventory.services import receive_stock
from people import services
from projects.models import Project, ProjectFile, ProjectStage, StageEvent, WorkflowStepTemplate, WorkflowTemplate

VALID_CODE_A, VALID_CODE_B = "0499370899", "0013542419"


class PeopleBase(TestCase):
    def setUp(self):
        cache.clear()   # throttle ردپا بین تست‌ها نشت نکند
        mk = User.objects.create_user
        self.manager = mk(username="p_mgr", password="pw", role=User.Role.ADMIN, phone_number="09130000001", is_superuser=False)
        self.superuser = User.objects.create_superuser(username="p_su", password="pw")
        self.accountant = mk(username="p_acc", password="pw", role=User.Role.EMPLOYEE, phone_number="09130000002")
        self.accountant.specialties.add(Specialty.objects.get_or_create(name="حسابدار")[0])
        self.tech = mk(username="09130000003", password="pw", role=User.Role.EMPLOYEE, phone_number="09130000003")
        self.other = mk(username="p_other", password="pw", role=User.Role.EMPLOYEE, phone_number="09130000004")
        self.client_user = mk(username="p_cli", password="pw", role=User.Role.CLIENT)
        self.party = Party.objects.create(name="مشتری افراد", is_client=True, phone_number="09130000009")
        self.client_user.party = self.party
        self.client_user.save()

    def login(self, user):
        c = Client()
        c.force_login(user)
        return c


class PresenceTests(PeopleBase):
    def test_get_200_is_recorded_with_view_name(self):
        self.login(self.tech).get(reverse("accounts:change_password"))
        p = UserPresence.objects.get(user=self.tech)
        self.assertEqual(p.view_name, "accounts:change_password")
        self.assertEqual(p.last_path, reverse("accounts:change_password"))

    def test_not_recorded_for_post_htmx_404_and_anonymous(self):
        c = self.login(self.tech)
        c.get(reverse("accounts:change_password"), HTTP_HX_REQUEST="true")
        c.post(reverse("accounts:change_password"), {})
        c.get("/no-such-page/")
        self.assertFalse(UserPresence.objects.exists())
        Client().get(reverse("accounts:login"))
        self.assertFalse(UserPresence.objects.exists())

    def test_throttled_for_same_page_but_other_page_updates(self):
        c = self.login(self.tech)
        c.get(reverse("accounts:change_password"))
        old = timezone.now() - timedelta(hours=1)
        UserPresence.objects.filter(user=self.tech).update(last_seen=old)
        c.get(reverse("accounts:change_password"))
        self.assertEqual(UserPresence.objects.get(user=self.tech).last_seen, old)
        c.get(reverse("accounts:password_reset_request"))
        self.assertNotEqual(UserPresence.objects.get(user=self.tech).last_seen, old)

    def test_labels_and_seen_text(self):
        self.assertEqual(services.page_label("projects:final_review"), "بازبینی نهایی")
        self.assertEqual(services.page_label("whatever:x"), "صفحه‌ی دیگر")
        self.assertEqual(services.seen_text(None), "هنوز دیده نشده")
        now = timezone.now()
        fresh = UserPresence(user=self.tech, last_seen=now - timedelta(minutes=1))
        old = UserPresence(user=self.tech, last_seen=now - timedelta(hours=2))
        self.assertEqual(services.seen_text(fresh, now), "همین حالا")
        self.assertNotEqual(services.seen_text(old, now), "همین حالا")


class PeopleAccessTests(PeopleBase):
    def test_view_pages_for_manager_and_accountant_only(self):
        urls = [reverse("people:staff"), reverse("people:staff_table"), reverse("people:customers"),
                reverse("people:customers_table"), reverse("people:user_detail", args=[self.tech.id]),
                reverse("people:party_detail", args=[self.party.id])]
        for user in (self.manager, self.accountant):
            c = self.login(user)
            for u in urls:
                self.assertEqual(c.get(u).status_code, 200, f"{user.username} {u}")
        for user in (self.tech, self.client_user):
            c = self.login(user)
            for u in urls:
                self.assertEqual(c.get(u).status_code, 404, f"{user.username} {u}")
        self.assertEqual(Client().get(urls[0]).status_code, 302)

    def test_edit_pages_and_actions_manager_only(self):
        edit = [reverse("people:user_edit", args=[self.tech.id]), reverse("people:party_edit", args=[self.party.id])]
        self.assertEqual([self.login(self.manager).get(u).status_code for u in edit], [200, 200])
        acc = self.login(self.accountant)
        self.assertEqual([acc.get(u).status_code for u in edit], [404, 404])
        before = self.tech.password
        self.assertEqual(acc.post(reverse("people:user_reset_password", args=[self.tech.id])).status_code, 404)
        self.assertEqual(acc.post(reverse("people:user_toggle_active", args=[self.tech.id]), {"reason": "x"}).status_code, 404)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.password, before)
        self.assertTrue(self.tech.is_active)

    def test_presence_and_feed_only_for_manager(self):
        UserPresence.objects.create(user=self.tech, last_seen=timezone.now(), last_path="/x/", view_name="home")
        mgr, acc = self.login(self.manager), self.login(self.accountant)
        self.assertContains(mgr.get(reverse("people:staff_table")), "آخرین دیده‌شدن")
        self.assertNotContains(acc.get(reverse("people:staff_table")), "آخرین دیده‌شدن")
        detail = reverse("people:user_detail", args=[self.tech.id])
        self.assertContains(mgr.get(detail), "فعالیت‌های اخیر")
        self.assertNotContains(acc.get(detail), "فعالیت‌های اخیر")

    def test_nav_links(self):
        url = reverse("accounts:change_password")
        for user, expected in ((self.manager, True), (self.accountant, True), (self.tech, False)):
            resp = self.login(user).get(url)
            self.assertEqual(reverse("people:staff") in resp.content.decode("utf-8"), expected, user.username)
            self.assertContains(resp, f'href="{url}"')


class UpdateProfileTests(PeopleBase):
    def upd(self, user=None, actor=None, **kw):
        data = dict(first_name="علی", last_name="رضایی", phone_number="09130000003", email="", national_code="")
        data.update(kw)
        return services.update_user_profile(user=user or self.tech, actor=actor or self.manager, **data)

    def test_update_fields_and_history_reason(self):
        self.upd(email="a@b.com", national_code=VALID_CODE_A)
        self.tech.refresh_from_db()
        self.assertEqual((self.tech.first_name, self.tech.email, self.tech.national_code), ("علی", "a@b.com", VALID_CODE_A))
        self.assertTrue(any("ویرایش اطلاعات" in h["reason"] for h in services.account_history(self.tech)))

    def test_username_follows_phone_only_when_it_was_the_phone(self):
        self.upd(phone_number="09130000099")
        self.tech.refresh_from_db()
        self.assertEqual((self.tech.phone_number, self.tech.username), ("09130000099", "09130000099"))
        self.upd(user=self.other, phone_number="09130000088", first_name="x")
        self.other.refresh_from_db()
        self.assertEqual(self.other.username, "p_other")

    def test_validation(self):
        for bad in ({"phone_number": "123"}, {"phone_number": "09130000004"}, {"email": "no"},
                    {"national_code": "1234567890"}, {"first_name": "", "last_name": ""}):
            with self.assertRaises(ValueError, msg=str(bad)):
                self.upd(**bad)
        self.upd(user=self.other, phone_number="09130000004", national_code=VALID_CODE_B)
        with self.assertRaises(ValueError):
            self.upd(national_code=VALID_CODE_B)

    def test_specialties_only_for_employee_and_none_means_untouched(self):
        sp = Specialty.objects.get_or_create(name="نصاب")[0]
        self.upd(specialty_ids=[str(sp.id)])
        self.assertEqual([s.name for s in self.tech.specialties.all()], ["نصاب"])
        self.upd(specialty_ids=None)
        self.assertEqual(self.tech.specialties.count(), 1)
        self.upd(specialty_ids=[])
        self.assertEqual(self.tech.specialties.count(), 0)

    def test_only_manager_and_superuser_guard(self):
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                self.upd(actor=actor)
        with self.assertRaises(ValueError):
            self.upd(user=self.superuser, actor=self.manager, phone_number="")
        self.upd(user=self.superuser, actor=self.superuser, first_name="مدیر ارشد", phone_number="")

    def test_edit_view_flow(self):
        c = self.login(self.manager)
        url = reverse("people:user_edit", args=[self.tech.id])
        r = c.post(url, {"first_name": "", "last_name": "", "phone_number": "09130000003"})
        self.assertEqual(r.status_code, 200)
        r = c.post(url, {"first_name": "نو", "last_name": "نام", "phone_number": "09130000003"})
        self.assertRedirects(r, reverse("people:user_detail", args=[self.tech.id]), fetch_redirect_response=False)
        self.tech.refresh_from_db()
        self.assertEqual(self.tech.first_name, "نو")


class ResetPasswordTests(PeopleBase):
    def test_reset_flow_shows_raw_once_and_forces_change(self):
        c = self.login(self.manager)
        r = c.post(reverse("people:user_reset_password", args=[self.tech.id]))
        self.assertEqual(r.status_code, 200)
        raw = r.context["raw_password"]
        self.assertIn("no-store", r["Cache-Control"])
        self.tech.refresh_from_db()
        self.assertTrue(check_password(raw, self.tech.password))
        self.assertTrue(self.tech.must_change_password)
        self.assertNotContains(c.get(reverse("people:user_detail", args=[self.tech.id])), raw)
        self.assertTrue(any("بازنشانی رمز" in h["reason"] for h in services.account_history(self.tech)))
        tc = self.login(self.tech)
        self.assertRedirects(tc.get(reverse("accounts:change_password")),
                             f"{reverse('accounts:force_set_password')}?next={reverse('accounts:change_password')}",
                             fetch_redirect_response=False)

    def test_guards(self):
        with self.assertRaises(ValueError):
            services.reset_user_password(user=self.tech, actor=self.accountant)
        with self.assertRaises(ValueError):
            services.reset_user_password(user=self.manager, actor=self.manager)
        with self.assertRaises(ValueError):
            services.reset_user_password(user=self.superuser, actor=self.manager)

    def test_force_set_password_has_no_skip_and_ignores_external_next(self):
        self.tech.must_change_password = True
        self.tech.save(update_fields=["must_change_password"])
        c = self.login(self.tech)
        self.assertNotContains(c.get(reverse("accounts:force_set_password")), 'name="skip"')
        r = c.post(reverse("accounts:force_set_password"), {
            "new_password1": "Str0ng-pass-99", "new_password2": "Str0ng-pass-99", "next": "https://evil.example/"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.tech.refresh_from_db()
        self.assertFalse(self.tech.must_change_password)


class ToggleActiveTests(PeopleBase):
    def test_reason_self_and_state_guards(self):
        with self.assertRaises(ValueError):
            services.set_user_active(user=self.tech, active=False, actor=self.manager, reason=" ")
        with self.assertRaises(ValueError):
            services.set_user_active(user=self.manager, active=False, actor=self.manager, reason="x")
        with self.assertRaises(ValueError):
            services.set_user_active(user=self.tech, active=True, actor=self.manager, reason="x")
        with self.assertRaises(ValueError):
            services.set_user_active(user=self.tech, active=False, actor=self.accountant, reason="x")

    def test_deactivate_returns_open_stage_count_and_blocks_access(self):
        tpl = WorkflowTemplate.objects.create(name="قالب افراد")
        step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="م")
        proj = Project.objects.create(name="پروژه افراد", partner=self.party, workflow_template=tpl,
                                      status=Project.Status.IN_PROGRESS)
        ProjectStage.objects.create(project=proj, step_template=step, order=1, title="م",
                                    status=ProjectStage.Status.IN_PROGRESS, assigned_to=self.tech)
        n = services.set_user_active(user=self.tech, active=False, actor=self.manager, reason="رفت")
        self.assertEqual(n, 1)
        self.assertEqual(self.login(self.tech).get(reverse("accounts:change_password")).status_code, 302)
        self.assertEqual(services.set_user_active(user=self.tech, active=True, actor=self.manager, reason="برگشت"), 0)
        self.assertTrue(any("غیرفعال" in h["reason"] for h in services.account_history(self.tech)))


class ActivityFeedTests(PeopleBase):
    def setUp(self):
        super().setUp()
        tpl = WorkflowTemplate.objects.create(name="قالب فید")
        self.step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="م")
        self.project = Project.objects.create(name="پروژه فید", partner=self.party, workflow_template=tpl,
                                              status=Project.Status.IN_PROGRESS, created_by=self.tech)
        self.stage = ProjectStage.objects.create(project=self.project, step_template=self.step, order=1, title="م",
                                                 status=ProjectStage.Status.IN_PROGRESS)

    def kinds(self, **kw):
        return {r["kind"] for r in services.activity_feed(self.tech, **kw)}

    def test_sources_and_order(self):
        StageEvent.objects.create(stage=self.stage, actor=self.tech, to_status="in_progress", comment="شروع")
        ProjectFile.objects.create(stage=self.stage, file="x.png", kind="image", original_name="x.png",
                                   uploaded_by=self.tech, is_attachment=True)
        item = Item.objects.create(name="کالای فید", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        wh = Warehouse.objects.create(name="انبار فید", is_default=True)
        receive_stock(item=item, warehouse=wh, qty=1, unit_cost=100, received_at=timezone.now(), created_by=self.tech)
        LoginHistory.objects.create(user=self.tech, username_attempted=self.tech.username, result="success")
        LoginHistory.objects.create(user=None, username_attempted=self.tech.phone_number, result="failed")
        LoginHistory.objects.create(user=None, username_attempted="someone_else", result="failed")
        feed = services.activity_feed(self.tech)
        self.assertEqual(self.kinds(), {"رویداد مرحله", "فایل", "حرکت انبار", "ورود", "ورود ناموفق", "ثبت پروژه"})
        self.assertEqual(sum(1 for r in feed if r["kind"] == "ورود ناموفق"), 1)
        times = [r["at"] for r in feed]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_days_window(self):
        e = StageEvent.objects.create(stage=self.stage, actor=self.tech, to_status="x", comment="قدیمی")
        StageEvent.objects.filter(pk=e.pk).update(created_at=timezone.now() - timedelta(days=40))
        self.assertNotIn("رویداد مرحله", self.kinds(days=30))
        self.assertIn("رویداد مرحله", self.kinds(days=90))

    def test_feed_not_shown_to_accountant_but_to_manager(self):
        StageEvent.objects.create(stage=self.stage, actor=self.tech, to_status="x", comment="کار عجیب‌وغریب")
        url = reverse("people:user_detail", args=[self.tech.id])
        self.assertContains(self.login(self.manager).get(url), "کار عجیب‌وغریب")
        self.assertNotContains(self.login(self.accountant).get(url), "کار عجیب‌وغریب")


class CustomersTests(PeopleBase):
    def setUp(self):
        super().setUp()
        self.project = Project.objects.create(name="پروژه مشتری افراد", partner=self.party, owner=self.party,
                                              status=Project.Status.IN_PROGRESS)
        self.invoice = Invoice.objects.create(project=self.project, number="INV-PP-1", billed_party=self.party,
                                              total_amount=Decimal("1000"), issue_date=timezone.localdate())

    def test_table_scope_and_outstanding(self):
        Party.objects.create(name="فقط تأمین‌کننده", is_supplier=True, phone_number="09130000011")
        Party.objects.filter(is_internal=True).update(is_partner=True)
        content = self.login(self.manager).get(reverse("people:customers_table")).content.decode("utf-8")
        self.assertIn("مشتری افراد", content)
        self.assertIn("۱,۰۰۰", content)
        self.assertNotIn("فقط تأمین‌کننده", content)
        self.assertNotIn("خودمان", content)

    def test_cancelled_invoice_not_counted(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(status=Invoice.Status.CANCELLED)
        self.assertNotIn("۱,۰۰۰", self.login(self.manager).get(reverse("people:customers_table")).content.decode("utf-8"))

    def test_profile_page_shows_invoice_payment_and_account(self):
        Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=100,
                               claimed_amount=100, reference_number="R")
        resp = self.login(self.accountant).get(reverse("people:party_detail", args=[self.party.id]))
        self.assertContains(resp, "INV-PP-1".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
        self.assertContains(resp, "پروژه مشتری افراد")
        self.assertContains(resp, reverse("people:user_detail", args=[self.client_user.id]))
        self.assertNotContains(resp, reverse("people:party_edit", args=[self.party.id]))

    def test_internal_party_profile_is_404(self):
        internal = Party.objects.filter(is_internal=True).first()
        self.assertEqual(self.login(self.manager).get(reverse("people:party_detail", args=[internal.id])).status_code, 404)

    def test_party_edit_service(self):
        services.update_party_profile(party=self.party, actor=self.manager, name="نام نو", brand_name="", phone_number="09130000009",
                                      secondary_phone="", email="", description="d", credit_limit_raw="۵,۰۰۰")
        self.party.refresh_from_db()
        self.assertEqual((self.party.name, self.party.credit_limit), ("نام نو", Decimal("5000")))
        other = Party.objects.create(name="دیگری", is_client=True, phone_number="09130000012")
        for kw in ({"phone_number": "09130000012"}, {"name": " "}, {"credit_limit_raw": "-5"}, {"email": "bad"}):
            data = dict(name="ن", brand_name="", phone_number="09130000009", secondary_phone="", email="",
                        description="", credit_limit_raw="0")
            data.update(kw)
            with self.assertRaises(ValueError, msg=str(kw)):
                services.update_party_profile(party=self.party, actor=self.manager, **data)
        with self.assertRaises(ValueError):
            services.update_party_profile(party=other, actor=self.accountant, name="x", brand_name="", phone_number="",
                                          secondary_phone="", email="", description="", credit_limit_raw="0")


class PeriodRowsCreditTests(PeopleBase):
    def test_pending_credit_payment_is_counted_in_its_month(self):
        row = accounting.period_rows(1)[0]
        start = jdatetime.date(row["year"], row["month"], 1).togregorian()
        project = Project.objects.create(name="پروژه ماه", partner=self.party, status=Project.Status.IN_PROGRESS)
        inv = Invoice.objects.create(project=project, number="INV-PR-1", billed_party=self.party,
                                     total_amount=Decimal("1000"), issue_date=timezone.localdate())
        pay = Payment.objects.create(invoice=inv, method=Payment.Method.CREDIT, amount=100, claimed_amount=100, note="x")
        Payment.objects.filter(pk=pay.pk).update(created_at=timezone.make_aware(datetime.combine(start, time(12))))
        self.assertEqual(accounting.period_rows(1)[0]["pending_count"], 1)
