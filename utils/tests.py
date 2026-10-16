from datetime import datetime, date, timezone as dt_timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
import jdatetime

from utils.jalali import jalali_str
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
        self.assertEqual(parsed_dt.astimezone(dt_timezone.utc), datetime(2026, 9, 20, 21, 0, tzinfo=dt_timezone.utc))

        # Invalid datetime
        with self.assertRaises(ValidationError):
            f_datetime.to_python("۱۴۰۵/۰۶/۳۰ ۲۵:۰۰")

    def test_project_and_invoice_shamsi_year(self):
        # بررسی پیشوند ماهانه در کد پروژه و فاکتور
        d = jdatetime.date.fromgregorian(date=timezone.localdate())
        expected_p_prefix = f"P{d.year % 100:02d}{d.month:02d}-"
        expected_inv_prefix = f"INV{d.year % 100:02d}{d.month:02d}-"

        party = Party.objects.create(name="شرکت الف", is_client=True)
        template = WorkflowTemplate.objects.create(name="قالب ۱")
        project = Project.objects.create(
            name="پروژه تست",
            partner=party,
            owner=party,
            workflow_template=template,
        )
        self.assertTrue(project.code.startswith(expected_p_prefix))

        inv_num = _generate_invoice_number()
        self.assertTrue(inv_num.startswith(expected_inv_prefix))

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
        ProjectStage.objects.create(
            project=proj1, step_template=step1, title="بازدید", order=1, client_visible=True, status=ProjectStage.Status.DONE
        )
        ProjectStage.objects.create(
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

        # باید لینک مراحل پروژه ۱ باشد
        progress_url = reverse("projects:portal_project_progress", args=[proj1.id])
        self.assertIn(progress_url, html)

        # باید لینک فاکتور متعلق به خود کاربر در صفحه باشد، اما نه فاکتور کاربر دیگر
        inv1_url = reverse("finance:portal_invoice_detail", args=[inv1.uuid])
        inv2_url = reverse("finance:portal_invoice_detail", args=[inv2.uuid])
        self.assertIn(inv1_url, html)
        self.assertNotIn(inv2_url, html)


class GenericTableAdvancedFilterUnitTests(TestCase):
    def test_select_filter_rejects_value_outside_choices(self):
        from django.test import RequestFactory
        from utils.generic_table import build_table_context

        User.objects.create_user(username="gtf_a", phone_number="09190004001", password="x", role="employee")
        User.objects.create_user(username="gtf_b", phone_number="09190004002", password="x", role="manager")

        request = RequestFactory().get("/fake/", {"f_role": "not-a-real-role"})
        ctx = build_table_context(
            request, User.objects.filter(phone_number__in=["09190004001", "09190004002"]),
            columns=[{"label": "نقش", "filter_key": "role", "filter_type": "select",
                      "choices": [("employee", "تکنسین"), ("manager", "مدیر")]}],
            row_builder=lambda u: {"url": None, "cells": [{"type": "text", "value": u.username}]},
            container_id="gtf-test-1",
        )
        self.assertEqual(ctx["active_filter_count"], 0)
        self.assertEqual(len(ctx["rows"]), 2)


class TestEnvironmentIsolationTests(TestCase):
    def test_no_real_sms_or_najva_credentials_during_tests(self):
        from django.conf import settings
        self.assertEqual(settings.SMS_IR_API_KEY, "")
        self.assertEqual(settings.SMS_IR_LINE_NUMBER, "")
        self.assertEqual(settings.NAJVA_API_KEY, "")
        self.assertEqual(settings.NAJVA_WEBSITE_ID, "")
        self.assertFalse(settings.NAJVA_ENABLED)
