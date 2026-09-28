import re
from datetime import datetime, date, timezone as dt_timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
import jdatetime

from utils.jalali import jalali_str, to_fa_digits
from utils.jalali_forms import JalaliDateField, JalaliDateTimeField
from accounts.models import User
from core.models import Party
from projects.models import Project, WorkflowTemplate, WorkflowStepTemplate, ProjectStage
from finance.models import Invoice
from finance.services import _generate_invoice_number


class JalaliAndUIWorkflowTests(TestCase):
    def test_jalali_str_conversion(self):
        # تست تبدیل با آگاهی از تایم‌زون
        dt_aware = datetime(2026, 9, 20, 21, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(jalali_str(dt_aware), "۱۴۰۵/۰۶/۳۰ ۰۰:۳۰")

        # تست تاریخ ساده
        d_simple = date(2026, 3, 21)
        self.assertEqual(jalali_str(d_simple), "۱۴۰۵/۰۱/۰۱")

    def test_jalali_fields_validation_and_parsing(self):
        # JalaliDateField tests
        f_date = JalaliDateField()
        # Parse persian digits LTR/RTL separators
        parsed_date = f_date.to_python("۱۴۰۵/۰۶/۳۰")
        self.assertEqual(parsed_date, date(2026, 9, 21))

        # Parse latin digits
        parsed_date_lat = f_date.to_python("1405-06-30")
        self.assertEqual(parsed_date_lat, date(2026, 9, 21))

        # Invalid dates
        with self.assertRaises(ValidationError):
            f_date.to_python("۱۴۰۵/۱۳/۰۱")
        with self.assertRaises(ValidationError):
            f_date.to_python("۱۴۰۵/۰۷/۳۱") # Mehr only has 30 days in jalali

        # prepare_value
        self.assertEqual(f_date.prepare_value(date(2026, 9, 21)), "۱۴۰۵/۰۶/۳۰")

        # has_changed
        self.assertFalse(f_date.has_changed(date(2026, 9, 21), "۱۴۰۵/۰۶/۳۰"))
        self.assertTrue(f_date.has_changed(date(2026, 9, 21), "۱۴۰۵/۰۶/۲۹"))

        # JalaliDateTimeField tests
        f_datetime = JalaliDateTimeField()
        # Parse datetime with tehran zone
        parsed_dt = f_datetime.to_python("۱۴۰۵/۰۶/۳۰ ۰۰:۳۰")
        # 1405/06/30 00:30 Tehran time (which is UTC+3:30 or DST)
        # 1405/06/30 is 2026-09-21. Wait, let's verify exact UTC equivalent
        # 2026-09-21 00:30 Tehran is indeed 2026-09-20 21:00 UTC
        self.assertEqual(parsed_dt.astimezone(dt_timezone.utc), datetime(2026, 9, 20, 21, 0, tzinfo=dt_timezone.utc))

        # Invalid datetime
        with self.assertRaises(ValidationError):
            f_datetime.to_python("۱۴۰۵/۰۶/۳۰ ۲۵:۰۰")

    def test_project_and_invoice_shamsi_year(self):
        # بررسی سال شمسی در کد پروژه و فاکتور
        current_shamsi_year = jdatetime.date.fromgregorian(date=timezone.localdate()).year
        
        party = Party.objects.create(name="شرکت الف", is_client=True)
        template = WorkflowTemplate.objects.create(name="قالب ۱")
        project = Project.objects.create(
            name="پروژه تست",
            partner=party,
            owner=party,
            workflow_template=template,
        )
        self.assertTrue(project.code.startswith(f"P{current_shamsi_year}-"))

        inv_num = _generate_invoice_number()
        self.assertTrue(inv_num.startswith(f"INV-{current_shamsi_year}-"))

    def test_login_page_antislop_and_content(self):
        client = Client()
        resp = client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        # نباید عبارات ۲۴ ساعته و چیلر در متن بازاریابی صفحه ورود باشد
        self.assertNotIn("۲۴ ساعته", content)
        self.assertNotIn("چیلر", content)
        self.assertIn("فرابخش تهویه", content)
        self.assertIn("کد پیامکی", content)

    def test_client_home_view_and_permissions(self):
        party1 = Party.objects.create(name="مشتری یک", is_client=True)
        party2 = Party.objects.create(name="مشتری دو", is_client=True)

        user1 = User.objects.create_user(
            username="client1",
            phone_number="09121112233",
            role=User.Role.CLIENT,
            party=party1,
        )
        template = WorkflowTemplate.objects.create(name="جریان کار")
        step1 = WorkflowStepTemplate.objects.create(template=template, title="مرحله اول", order=1)
        step2 = WorkflowStepTemplate.objects.create(template=template, title="مرحله دوم", order=2)

        proj1 = Project.objects.create(
            name="پروژه آزمایشی مشتری ۱",
            partner=party1,
            owner=party1,
            workflow_template=template,
        )
        # stages ساخته می‌شوند در متد setup_stages_from_template یا دستی
        stage1 = ProjectStage.objects.create(
            project=proj1, step_template=step1, title="بازدید", order=1, client_visible=True, status=ProjectStage.Status.DONE
        )
        stage2 = ProjectStage.objects.create(
            project=proj1, step_template=step2, title="طراحی", order=2, client_visible=True, status=ProjectStage.Status.IN_PROGRESS
        )

        # فاکتور متعلق به کاربر
        inv1 = Invoice.objects.create(
            number=_generate_invoice_number(),
            project=proj1,
            billed_party=party1,
            total_amount=5000000,
            issue_date=timezone.localdate(),
        )

        # فاکتور پروژه دیگر برای کاربر دیگر
        proj2 = Project.objects.create(
            name="پروژه مشتری ۲",
            partner=party2,
            owner=party2,
            workflow_template=template,
        )
        inv2 = Invoice.objects.create(
            number=_generate_invoice_number(),
            project=proj2,
            billed_party=party2,
            total_amount=8000000,
            issue_date=timezone.localdate(),
        )

        client = Client()
        client.force_login(user1)
        resp = client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # نباید «کارفرما»، «گارانتی» و «خدمات تخصصی» در صفحه باشد
        self.assertNotIn("کارفرما", html)
        self.assertNotIn("گارانتی", html)
        self.assertNotIn("خدمات تخصصی", html)

        # باید لینک مراحل پروژه ۱ باشد
        progress_url = reverse("projects:portal_project_progress", args=[proj1.id])
        self.assertIn(progress_url, html)

        # باید لینک فاکتور متعلق به خود کاربر در صفحه باشد، اما نه فاکتور کاربر دیگر
        inv1_url = reverse("finance:portal_invoice_detail", args=[inv1.uuid])
        inv2_url = reverse("finance:portal_invoice_detail", args=[inv2.uuid])
        self.assertIn(inv1_url, html)
        self.assertNotIn(inv2_url, html)

    def test_admin_add_user_page_renders_200(self):
        admin_user = User.objects.create_superuser(
            username="adminuser",
            phone_number="09129999999",
            password="AdminPassword123",
            role=User.Role.ADMIN,
        )
        client = Client()
        client.force_login(admin_user)
        resp = client.get(reverse("admin:accounts_user_add"))
        self.assertEqual(resp.status_code, 200)

    def test_admin_invoice_shamsi_change_and_readonly(self):
        admin_user = User.objects.create_superuser(
            username="superadmin",
            phone_number="09128888888",
            password="AdminPassword123",
            role=User.Role.ADMIN,
        )
        party = Party.objects.create(name="مشتری تست ادمین", is_client=True)
        template = WorkflowTemplate.objects.create(name="قالب ۱")
        project = Project.objects.create(name="پروژه تست ادمین", partner=party, owner=party, workflow_template=template)
        invoice = Invoice.objects.create(
            number=_generate_invoice_number(),
            project=project,
            billed_party=party,
            total_amount=1000000,
            issue_date=date(2026, 9, 21), # ۱۴۰۵/۰۶/۳۰
        )

        client = Client()
        client.force_login(admin_user)
        change_url = reverse("admin:finance_invoice_change", args=[invoice.pk])
        resp = client.get(change_url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # issue_date شمسی با ارقام لاتین و خط تیره رندر می‌شود (مقدار ورودی پکیج: 1405-06-30)
        self.assertIn("1405-06-30", html)

        # settled_at در فیلدهای فرم نباشد
        self.assertNotIn('name="settled_at"', html)

        # ارسال یک تاریخ شمسی معتبر برای issue_date و ذخیره تاریخ میلادی درست
        post_data = {
            "number": invoice.number,
            "project": project.pk,
            "billed_party": party.pk,
            "document_type": invoice.document_type,
            "status": invoice.status,
            "issue_date": "1405-07-01", # برابر با 2026-09-23
            "contract_date": "1405-07-01",
            "notes": "یادداشت تست",
            "lines-TOTAL_FORMS": "0",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "payments-TOTAL_FORMS": "0",
            "payments-INITIAL_FORMS": "0",
            "payments-MIN_NUM_FORMS": "0",
            "payments-MAX_NUM_FORMS": "1000",
        }
        post_resp = client.post(change_url, post_data)
        self.assertEqual(post_resp.status_code, 302)

        invoice.refresh_from_db()
        self.assertEqual(invoice.issue_date, date(2026, 9, 23))

    def test_stray_characters_regex(self):
        # بررسی عدم وجود کاراکترهای مخرب در تمپلیت‌ها
        # تست regex گام ۱
        client = Client()
        
        party = Party.objects.create(name="مشتری تست کاراکتر", is_client=True)
        user = User.objects.create_user(username="client_char", phone_number="09121234567", role=User.Role.CLIENT, party=party)
        template = WorkflowTemplate.objects.create(name="قالب")
        project = Project.objects.create(name="پروژه", partner=party, owner=party, workflow_template=template)
        invoice = Invoice.objects.create(number=_generate_invoice_number(), project=project, billed_party=party, total_amount=2000000, issue_date=timezone.localdate())
        from finance.models import InvoiceLine
        InvoiceLine.objects.create(invoice=invoice, title="هزینه ردیف تستی", qty=1, unit_price=2000000, total=2000000)

        pattern_stray_slash = re.compile(r"(?m)^\s*/\s*$")
        pattern_stray_closing_slash = re.compile(r"(?m)>/\s*$")

        # صفحه اصلی برای کاربر وارد شده
        client.force_login(user)
        resp_home = client.get(reverse("home"))
        self.assertEqual(resp_home.status_code, 200)
        home_html = resp_home.content.decode("utf-8")
        self.assertIsNone(pattern_stray_slash.search(home_html), "Stray / found in home HTML")
        self.assertIsNone(pattern_stray_closing_slash.search(home_html), "Stray >/ found in home HTML")

        # صفحه فاکتور دارای ردیف
        inv_url = reverse("finance:portal_invoice_detail", args=[invoice.uuid])
        resp_inv = client.get(inv_url)
        self.assertEqual(resp_inv.status_code, 200)
        inv_html = resp_inv.content.decode("utf-8")
        self.assertIsNone(pattern_stray_slash.search(inv_html), "Stray / found in portal invoice HTML")
        self.assertIsNone(pattern_stray_closing_slash.search(inv_html), "Stray >/ found in portal invoice HTML")


class TableUrlTagTests(TestCase):
    def test_table_url_overrides_multiple_keys_and_preserves_rest(self):
        from django.test import RequestFactory
        from django.template import Context, Template
        request = RequestFactory().get("/fake/?mt_q=test&mt_page=3&other=1")
        tpl = Template("{% load custom_tags %}{% table_url 'mt_sort' 'name' 'mt_page' 1 %}")
        rendered = tpl.render(Context({"request": request}))
        self.assertIn("mt_q=test", rendered)
        self.assertIn("other=1", rendered)
        self.assertIn("mt_sort=name", rendered)
        self.assertIn("mt_page=1", rendered)

    def test_sort_next_dir(self):
        from utils.templatetags.custom_tags import sort_next_dir
        self.assertEqual(sort_next_dir("name", "asc", "name"), "desc")
        self.assertEqual(sort_next_dir("name", "desc", "name"), "asc")
        self.assertEqual(sort_next_dir("other", "asc", "name"), "asc")


class GenericTableAdvancedFilterUnitTests(TestCase):
    def test_select_filter_rejects_value_outside_choices(self):
        from django.test import RequestFactory
        from utils.generic_table import build_table_context
        from accounts.models import User as UserModel

        UserModel.objects.create_user(username="gtf_a", phone_number="09190004001", password="x", role="employee")
        UserModel.objects.create_user(username="gtf_b", phone_number="09190004002", password="x", role="manager")

        request = RequestFactory().get("/fake/", {"f_role": "not-a-real-role"})
        ctx = build_table_context(
            request, UserModel.objects.filter(phone_number__in=["09190004001", "09190004002"]),
            columns=[{"label": "نقش", "filter_key": "role", "filter_type": "select",
                      "choices": [("employee", "تکنسین"), ("manager", "مدیر")]}],
            row_builder=lambda u: {"url": None, "cells": [{"type": "text", "value": u.username}]},
            container_id="gtf-test-1",
        )
        self.assertEqual(ctx["active_filter_count"], 0)
        self.assertEqual(len(ctx["rows"]), 2)

    def test_number_range_filter_applies_correctly(self):
        from django.test import RequestFactory
        from utils.generic_table import build_table_context
        from core.models import Party

        Party.objects.create(name="طرف کم", credit_limit=1000, is_client=True, national_code="1010101010")
        Party.objects.create(name="طرف زیاد", credit_limit=90000, is_client=True, national_code="2020202020")

        request = RequestFactory().get("/fake/", {"fmin_credit": "5000"})
        ctx = build_table_context(
            request, Party.objects.all(),
            columns=[{"label": "سقف اعتبار", "filter_key": "credit", "filter_type": "number_range",
                      "filter_field": "credit_limit"}],
            row_builder=lambda p: {"url": None, "cells": [{"type": "text", "value": p.name}]},
            container_id="gtf-test-2",
        )
        self.assertEqual(len(ctx["rows"]), 1)
        self.assertEqual(ctx["active_filter_count"], 1)

    def test_reset_url_drops_only_this_tables_own_params(self):
        from django.test import RequestFactory
        from utils.generic_table import build_table_context
        from core.models import Party

        request = RequestFactory().get("/fake/", {
            "py_sort": "name", "py_dir": "desc", "py_f_is_client": "1", "other_page": "3",
        })
        ctx = build_table_context(
            request, Party.objects.none(),
            columns=[{"label": "نام", "sort_field": "name", "filter_key": "is_client", "filter_type": "boolean"}],
            row_builder=lambda p: {"url": None, "cells": []},
            container_id="gtf-test-3",
            param_prefix="py_",
        )
        self.assertNotIn("py_sort", ctx["reset_url"])
        self.assertNotIn("py_f_is_client", ctx["reset_url"])
        self.assertIn("other_page=3", ctx["reset_url"])

    def test_table_without_filter_types_still_gets_sort_modal(self):
        from django.test import RequestFactory
        from utils.generic_table import build_table_context
        from core.models import Party

        request = RequestFactory().get("/fake/")
        ctx = build_table_context(
            request, Party.objects.none(),
            columns=[{"label": "نام", "sort_field": "name"}],
            row_builder=lambda p: {"url": None, "cells": []},
            container_id="gtf-test-4",
        )
        self.assertTrue(ctx["has_modal"])
        self.assertEqual(ctx["active_filter_count"], 0)


class TabsEngineTests(TestCase):
    def test_resolve_active_tab_defaults_to_first_when_missing(self):
        from django.test import RequestFactory
        from utils.tabs import resolve_active_tab
        request = RequestFactory().get("/")
        self.assertEqual(resolve_active_tab(request, ["a", "b", "c"]), "a")

    def test_resolve_active_tab_reads_valid_param(self):
        from django.test import RequestFactory
        from utils.tabs import resolve_active_tab
        request = RequestFactory().get("/", {"tab": "b"})
        self.assertEqual(resolve_active_tab(request, ["a", "b", "c"]), "b")

    def test_resolve_active_tab_ignores_invalid_value(self):
        from django.test import RequestFactory
        from utils.tabs import resolve_active_tab
        request = RequestFactory().get("/", {"tab": "not-real"})
        self.assertEqual(resolve_active_tab(request, ["a", "b", "c"]), "a")

    def test_build_tabs_context_marks_correct_tab_active(self):
        from django.test import RequestFactory
        from utils.tabs import build_tabs_context
        request = RequestFactory().get("/", {"tab": "second"})
        ctx = build_tabs_context(request, [
            {"key": "first", "label": "اول", "url": "/x/", "container_id": "c1"},
            {"key": "second", "label": "دوم", "url": "/y/", "container_id": "c2"},
        ])
        self.assertFalse(ctx["tabs"][0]["is_active"])
        self.assertTrue(ctx["tabs"][1]["is_active"])
        self.assertEqual(ctx["active_tab_key"], "second")

    def test_eager_render_called_only_for_active_tab(self):
        from django.test import RequestFactory
        from utils.tabs import build_tabs_context
        calls = {"first": 0, "second": 0}

        def make_render(name):
            def _r():
                calls[name] += 1
                return f"<p>{name}</p>"
            return _r

        request = RequestFactory().get("/", {"tab": "second"})
        ctx = build_tabs_context(request, [
            {"key": "first", "label": "اول", "url": "/x/", "container_id": "c1", "eager_render": make_render("first")},
            {"key": "second", "label": "دوم", "url": "/y/", "container_id": "c2", "eager_render": make_render("second")},
        ])
        self.assertEqual(calls["first"], 0)
        self.assertEqual(calls["second"], 1)
        self.assertIsNone(ctx["tabs"][0]["eager_html"])
        self.assertIn("second", ctx["tabs"][1]["eager_html"])

    def test_count_builder_called_for_every_tab_regardless_of_active(self):
        from django.test import RequestFactory
        from utils.tabs import build_tabs_context
        request = RequestFactory().get("/")
        ctx = build_tabs_context(request, [
            {"key": "a", "label": "آ", "url": "/x/", "container_id": "c1", "count_builder": lambda: 5},
            {"key": "b", "label": "ب", "url": "/y/", "container_id": "c2", "count_builder": lambda: 9},
        ])
        self.assertEqual(ctx["tabs"][0]["count"], 5)
        self.assertEqual(ctx["tabs"][1]["count"], 9)

    def test_tab_without_count_builder_has_none_count(self):
        from django.test import RequestFactory
        from utils.tabs import build_tabs_context
        request = RequestFactory().get("/")
        ctx = build_tabs_context(request, [{"key": "a", "label": "آ", "url": "/x/", "container_id": "c1"}])
        self.assertIsNone(ctx["tabs"][0]["count"])


class TableToolbarRegressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="ttr_admin", phone_number="09190006001",
            password="Test@1234", role=User.Role.ADMIN, is_superuser=True,
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.url = reverse("finance:payments_table")

    def test_no_live_search_trigger_and_has_submit_icon(self):
        content = self.client.get(self.url).content.decode("utf-8")
        self.assertNotIn('hx-trigger="input changed', content)
        self.assertIn('type="submit"', content)
        self.assertIn('aria-label="جستجو"', content)

    def test_sort_header_targets_partial_endpoint_not_current_page(self):
        content = self.client.get(self.url).content.decode("utf-8")
        self.assertNotIn('hx-get="?', content)
        self.assertIn('hx-get="/payments/table/?py_sort=', content)

    def test_no_hardcoded_push_url_attribute_in_table(self):
        content = self.client.get(self.url).content.decode("utf-8")
        self.assertNotIn("hx-push-url", content)

    def test_search_form_preserves_sort_filter_and_resets_page(self):
        content = self.client.get(self.url, {
            "py_sort": "amount", "py_dir": "desc", "py_f_method": "credit", "py_page": "3", "py_q": "x",
        }).content.decode("utf-8")
        self.assertIn('name="py_sort" value="amount"', content)
        self.assertIn('name="py_f_method" value="credit"', content)
        self.assertNotIn('name="py_page" value="3"', content)
        self.assertIn('name="py_page" value="1"', content)

    def test_push_url_header_targets_host_page_and_merges_params(self):
        from urllib.parse import urlsplit, parse_qs
        resp = self.client.get(
            self.url, {"py_q": "abc"},
            headers={"HX-Request": "true",
                     "HX-Current-URL": "http://testserver/payments/?py_page=3&other=1&tab=claimable"},
        )
        parts = urlsplit(resp["HX-Push-Url"])
        self.assertEqual(parts.path, "/payments/")
        self.assertEqual(parse_qs(parts.query), {"other": ["1"], "py_q": ["abc"], "tab": ["claimable"]})

    def test_tab_click_request_sets_new_tab_in_push_url(self):
        from urllib.parse import urlsplit, parse_qs
        resp = self.client.get(
            self.url, {"tab": "stock"},
            headers={"HX-Request": "true", "HX-Current-URL": "http://testserver/?tab=my_tasks"},
        )
        self.assertEqual(parse_qs(urlsplit(resp["HX-Push-Url"]).query), {"tab": ["stock"]})

    def test_no_push_header_without_htmx(self):
        resp = self.client.get(self.url)
        self.assertNotIn("HX-Push-Url", resp.headers)


