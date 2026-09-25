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
