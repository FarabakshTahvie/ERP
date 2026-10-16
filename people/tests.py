from decimal import Decimal

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserPresence
from core.models import Party, Specialty
from finance.models import Invoice
from people import services
from projects.models import Project, ProjectStage, StageEvent, WorkflowStepTemplate, WorkflowTemplate

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
    def test_not_recorded_for_post_htmx_404_and_anonymous(self):
        c = self.login(self.tech)
        c.get(reverse("accounts:change_password"), HTTP_HX_REQUEST="true")
        c.post(reverse("accounts:change_password"), {})
        c.get("/no-such-page/")
        self.assertFalse(UserPresence.objects.exists())
        Client().get(reverse("accounts:login"))
        self.assertFalse(UserPresence.objects.exists())


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


class UpdateProfileTests(PeopleBase):
    def upd(self, user=None, actor=None, **kw):
        data = dict(first_name="علی", last_name="رضایی", phone_number="09130000003", email="", national_code="")
        data.update(kw)
        return services.update_user_profile(user=user or self.tech, actor=actor or self.manager, **data)

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

    def test_only_manager_and_superuser_guard(self):
        for actor in (self.accountant, self.tech):
            with self.assertRaises(ValueError):
                self.upd(actor=actor)
        with self.assertRaises(ValueError):
            self.upd(user=self.superuser, actor=self.manager, phone_number="")
        self.upd(user=self.superuser, actor=self.superuser, first_name="مدیر ارشد", phone_number="")


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
        self.assertIsNone(ProjectStage.objects.get(assigned_to__isnull=True).assigned_to)
        self.assertEqual(self.login(self.tech).get(reverse("accounts:change_password")).status_code, 302)
        self.assertEqual(services.set_user_active(user=self.tech, active=True, actor=self.manager, reason="برگشت"), 0)
        self.assertTrue(any("غیرفعال" in h["reason"] for h in services.account_history(self.tech)))

    def test_deactivate_returns_stage_to_specialty_pool(self):
        sp = Specialty.objects.get_or_create(name="کانال‌کش")[0]
        self.tech.specialties.add(sp)
        mate = User.objects.create_user(username="p_mate", password="pw", role=User.Role.EMPLOYEE)
        mate.specialties.add(sp)
        tpl = WorkflowTemplate.objects.create(name="قالب استخر")
        step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="م", responsible_specialty=sp)
        proj = Project.objects.create(name="پروژه استخر", partner=self.party, workflow_template=tpl,
                                      status=Project.Status.IN_PROGRESS)
        st = ProjectStage.objects.create(project=proj, step_template=step, order=1, title="م",
                                         status=ProjectStage.Status.IN_PROGRESS, assigned_to=self.tech)
        services.set_user_active(user=self.tech, active=False, actor=self.manager, reason="رفت")
        st.refresh_from_db()
        self.assertIsNone(st.assigned_to)
        self.assertEqual(list(st.candidate_users.all()), [mate])


class ActivityFeedTests(PeopleBase):
    def setUp(self):
        super().setUp()
        tpl = WorkflowTemplate.objects.create(name="قالب فید")
        self.step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="م")
        self.project = Project.objects.create(name="پروژه فید", partner=self.party, workflow_template=tpl,
                                              status=Project.Status.IN_PROGRESS, created_by=self.tech)
        self.stage = ProjectStage.objects.create(project=self.project, step_template=self.step, order=1, title="م",
                                                 status=ProjectStage.Status.IN_PROGRESS)

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
        from utils.test_helpers import confirm_invoice
        confirm_invoice(self.invoice)

    def test_unconfirmed_proforma_is_not_debt(self):
        other = Party.objects.create(name="شریک بی‌تایید", is_partner=True, phone_number="09130000013")
        proj = Project.objects.create(name="پروژه بی‌تایید", partner=other, owner=other, status=Project.Status.IN_PROGRESS)
        Invoice.objects.create(project=proj, number="INV-PP-9", billed_party=other,
                               total_amount=Decimal("7777"), issue_date=timezone.localdate())
        content = self.login(self.manager).get(reverse("people:customers_table")).content.decode("utf-8")
        self.assertIn("شریک بی‌تایید", content)
        self.assertNotIn("۷,۷۷۷", content)

    def test_cancelled_invoice_not_counted(self):
        Invoice.objects.filter(pk=self.invoice.pk).update(status=Invoice.Status.CANCELLED)
        self.assertNotIn("۱,۰۰۰", self.login(self.manager).get(reverse("people:customers_table")).content.decode("utf-8"))

    def test_internal_party_profile_is_404(self):
        internal = Party.objects.filter(is_internal=True).first()
        self.assertEqual(self.login(self.manager).get(reverse("people:party_detail", args=[internal.id])).status_code, 404)
