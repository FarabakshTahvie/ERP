import io
from decimal import Decimal
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate, StageApproval
from projects.services import create_project_from_technician_intake
from finance.models import Invoice, Payment
from finance.services import (
    create_customer_payment, approve_payment, reject_payment,
    PROOF_METHODS, CUSTOMER_METHODS,
)
from finance.admin import PaymentAdmin
from finance.forms import PaymentInlineForm
from django.contrib.admin.sites import AdminSite
from utils.test_helpers import make_image_file


class PaymentTests(TestCase):
    def setUp(self):
        self.tech_creator = User.objects.create_user(
            username="tech_creator_pay", phone_number="09120000091",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.other_tech = User.objects.create_user(
            username="tech_other_pay", phone_number="09120000092",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.admin_user = User.objects.create_user(
            username="admin_user_pay", phone_number="09120000093",
            password="AdminPassword123", role=User.Role.ADMIN,
        )
        self.client_user = User.objects.create_user(
            username="client_user_pay", phone_number="09120000094",
            password="ClientPassword123", role=User.Role.CLIENT,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.tech_creator.specialties.add(self.sp_reception)
        self.other_tech.specialties.add(self.sp_reception)
        self.accountant = User.objects.create_user(
            username="acc_user_pay", phone_number="09120000095",
            password="AccPassword123", role=User.Role.EMPLOYEE,
        )
        self.accountant.specialties.add(self.sp_accountant)

        self.party = Party.objects.create(name="کارفرمای تست پرداخت", phone_number="09120000094", is_client=True)
        self.client_user.party = self.party
        self.client_user.save()

        self.template = WorkflowTemplate.objects.create(name="قالب تست مالی", is_default=True)
        self.step1 = WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="صدور پیش‌فاکتور",
        )
        self.step2 = WorkflowStepTemplate.objects.create(
            template=self.template, order=2, title="تایید پیش‌فاکتور", requires_payment_selection=True,
        )

        self.service1 = Service.objects.create(name="خدمت تست مالی")
        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.tech_creator,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            material_lines=[],
            send_sms=False,
        )
        # مانده اولیه: 1,000,000 تومان

        self.sample_image = make_image_file("receipt.png")

    # ۱. الزامات ثبت مشتری
    def test_customer_payment_requirements(self):
        # کارت به کارت: فقط شماره پیگیری مجاز است
        pay_ref_only = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, reference_number="123456",
        )
        self.assertEqual(pay_ref_only.reference_number, "123456")
        self.assertFalse(pay_ref_only.receipt_file)
        pay_ref_only.delete()

        # کارت به کارت: فقط تصویر مجاز است
        img = make_image_file("c2c.png")
        pay_img_only = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, receipt_file=img,
        )
        self.assertTrue(bool(pay_img_only.receipt_file))
        pay_img_only.delete()

        # کارت به کارت: هیچ‌کدام خطا می‌دهد
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD)
        self.assertIn("حداقل یکی از", str(ctx.exception))

        # رسید واریز و چک: بدون تصویر خطا می‌دهد
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(invoice=self.invoice, method=Payment.Method.RECEIPT, reference_number="123")
        self.assertIn("آپلود تصویر رسید/چک الزامی است", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CHEQUE)
        self.assertIn("آپلود تصویر رسید/چک الزامی است", str(ctx.exception))

        cheque_img = make_image_file("cheque.png")
        cheque_pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CHEQUE, receipt_file=cheque_img,
        )
        self.assertEqual(cheque_pay.method, Payment.Method.CHEQUE)
        cheque_pay.delete()

        # اعتباری: تصویر یا پیگیری نادیده گرفته می‌شود و ذخیره نمی‌شود
        credit_img = make_image_file("credit.png")
        credit_pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CREDIT, note="تسویه تا آخر ماه",
            receipt_file=credit_img, reference_number="IGNORE_ME",
        )
        self.assertEqual(credit_pay.method, Payment.Method.CREDIT)
        self.assertFalse(credit_pay.receipt_file)
        self.assertEqual(credit_pay.reference_number, "")
        credit_pay.delete()

        # اعتباری بدون توضیح خطا می‌دهد
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="")
        self.assertIn("توضیح الزامی است", str(ctx.exception))

    # ۲. ثبت تکراری (جلوگیری از دابل‌کلیک در ۶۰ ثانیه)
    def test_duplicate_payment_prevention(self):
        create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="200000", reference_number="DUP-1",
        )
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(
                invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
                amount_raw="200000", reference_number="DUP-1",
            )
        self.assertIn("همین پرداخت لحظاتی پیش ثبت شده است", str(ctx.exception))
        self.assertEqual(Payment.objects.filter(reference_number="DUP-1").count(), 1)

    # ۳. اعتبارسنجی مبلغ
    def test_payment_amount_validation(self):
        with self.assertRaises(ValueError):
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="abc")
        with self.assertRaises(ValueError):
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="0")
        with self.assertRaises(ValueError):
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="-500")
        with self.assertRaises(ValueError):
            create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="2000000")

        pay = create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="۱,۰۰۰")
        self.assertEqual(pay.amount, Decimal("1000"))
        self.assertEqual(pay.claimed_amount, Decimal("1000"))
        pay.delete()

        pay_full = create_customer_payment(invoice=self.invoice, method=Payment.Method.CREDIT, note="تست", amount_raw="")
        self.assertEqual(pay_full.amount, Decimal("1000000"))
        self.assertEqual(pay_full.claimed_amount, Decimal("1000000"))
        pay_full.delete()

    # ۴. اعتبارسنجی فایل و حجم ۲۰ مگابایت
    def test_file_extension_and_size(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad_file = SimpleUploadedFile("danger.exe", b"executable content", content_type="application/octet-stream")
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(
                invoice=self.invoice, method=Payment.Method.RECEIPT,
                reference_number="123", receipt_file=bad_file,
            )
        self.assertIn("فرمت فایل رسید مجاز نیست", str(ctx.exception))

        big_file = SimpleUploadedFile("huge.jpg", b"x" * (11 * 1024 * 1024), content_type="image/jpeg")
        with self.assertRaises(ValueError) as ctx:
            create_customer_payment(
                invoice=self.invoice, method=Payment.Method.RECEIPT,
                reference_number="123", receipt_file=big_file,
            )
        self.assertIn("بیشتر از ۱۰ مگابایت", str(ctx.exception))

    # ۵. rejection_reason
    def test_rejection_reason_property(self):
        pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="300000", reference_number="REF-REJ", note="توضیح مشتری",
        )
        self.assertEqual(pay.rejection_reason, "")

        reject_payment(pay, rejected_by=self.admin_user, reason="مبلغ واریزی تطبیق ندارد")
        pay.refresh_from_db()
        self.assertEqual(pay.status, Payment.Status.REJECTED)
        self.assertEqual(pay.rejection_reason, "مبلغ واریزی تطبیق ندارد")
        self.assertIn("توضیح مشتری", pay.note)

    # ۶. فرم ادمین
    def test_admin_payment_inline_form(self):
        # کارت‌به‌کارت با پیگیری و بدون فایل معتبر است
        form = PaymentInlineForm(data={
            "invoice": self.invoice.id,
            "method": "card_to_card",
            "amount": "200000",
            "reference_number": "TRX-ADM-1",
            "status": "pending",
        })
        self.assertTrue(form.is_valid(), msg=str(form.errors))

        # چک بدون فایل نامعتبر است
        form2 = PaymentInlineForm(data={
            "invoice": self.invoice.id,
            "method": "cheque",
            "amount": "200000",
            "status": "pending",
        })
        self.assertFalse(form2.is_valid())
        self.assertIn("برای رسید واریز و چک، آپلود تصویر رسید/چک الزامی است.", str(form2.errors))

    # ۷. تایید پرداخت
    def test_approve_payment_rules(self):
        img = make_image_file("pay7.png")
        pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="600000", reference_number="REF-1", receipt_file=img,
        )

        with self.assertRaises(ValueError) as ctx:
            approve_payment(pay, approved_by=self.admin_user)
        self.assertIn("مبلغ واقعی را از روی رسید وارد کنید", str(ctx.exception))
        pay.refresh_from_db()
        self.assertEqual(pay.status, Payment.Status.PENDING)

        with self.assertRaises(ValueError) as ctx:
            approve_payment(pay, approved_by=self.admin_user, verified_amount="1500000")
        self.assertIn("بیشتر است", str(ctx.exception))

        approve_payment(pay, approved_by=self.admin_user, verified_amount="550000")
        pay.refresh_from_db()
        self.assertEqual(pay.status, Payment.Status.APPROVED)
        self.assertEqual(pay.amount, Decimal("550000"))
        self.assertEqual(pay.claimed_amount, Decimal("600000"))

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("550000"))

        credit_pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CREDIT,
            amount_raw="400000", note="باقی‌مانده اعتباری",
        )
        approve_payment(credit_pay, approved_by=self.admin_user)
        credit_pay.refresh_from_db()
        self.assertEqual(credit_pay.status, Payment.Status.APPROVED)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount, Decimal("550000"))

    # ۸. قفل تصمیم
    def test_decision_lock(self):
        img = make_image_file("pay8.png")
        pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="300000", reference_number="REF-2", receipt_file=img,
        )
        approve_payment(pay, approved_by=self.admin_user, verified_amount="300000")

        with self.assertRaises(ValueError):
            approve_payment(pay, approved_by=self.admin_user, verified_amount="300000")
        with self.assertRaises(ValueError):
            reject_payment(pay, rejected_by=self.admin_user, reason="دلیل")

    # ۹. ویوهای مدیریت و دسترسی
    def test_payment_views_and_permissions(self):
        client = Client()
        img = make_image_file("pay9.png")
        pay = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="200000", reference_number="REF-4", receipt_file=img,
        )
        detail_url = reverse("finance:payment_detail", args=[pay.id])
        decide_url = reverse("finance:payment_decide", args=[pay.id])

        # تکنسین ثبت‌کننده‌ی پروژه (دیگر دسترسی پرداخت ندارد و ۳۰۲ می‌گیرد)
        client.force_login(self.tech_creator)
        self.assertEqual(client.get(detail_url).status_code, 302)

        # حسابدار: جزئیات را می‌بیند
        client.force_login(self.accountant)
        self.assertEqual(client.get(detail_url).status_code, 200)

        # تکنسین دیگر (ثبت‌کننده نیست): نه جزئیات، نه تصمیم
        client.force_login(self.other_tech)
        self.assertEqual(client.get(detail_url).status_code, 302)
        resp_decide = client.post(decide_url, {"action": "approve", "verified_amount": "200000"})
        self.assertEqual(resp_decide.status_code, 302)
        pay.refresh_from_db()
        self.assertEqual(pay.status, Payment.Status.PENDING)

        # مشتری: user_passes_test او را ریدایرکت می‌کند
        client.force_login(self.client_user)
        self.assertEqual(client.get(detail_url).status_code, 302)

        # مدیر
        client.force_login(self.admin_user)
        self.assertEqual(client.get(detail_url).status_code, 200)

    # ۱۰. مسیر مشتری: add_payment و portal_stage_approval
    def test_client_portal_payment_flow(self):
        client = Client()
        client.force_login(self.client_user)

        # add_payment با کارت به کارت بدون فایل و بدون پیگیری پرداختی نمی‌سازد
        resp = client.post(reverse("finance:portal_add_payment", args=[self.invoice.uuid]), {
            "payment_method": "card_to_card",
            "payment_amount": "500000",
            "reference_number": "",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Payment.objects.filter(claimed_amount=500000).exists())

        stage2 = self.project.stages.get(order=2)
        stage2.status = ProjectStage.Status.WAITING_APPROVAL
        stage2.save()
        approval = StageApproval.objects.create(stage=stage2, sent_to_party=self.party)

        resp2 = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), {
            "action": "approve",
            "payment_method": "card_to_card",
            "payment_amount": "500000",
            "reference_number": "",
            "seen_total": str(int(self.invoice.total_amount)),
        })
        self.assertEqual(resp2.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, StageApproval.Decision.PENDING)
        self.assertFalse(Payment.objects.filter(claimed_amount=500000).exists())


class PaymentsTableSearchSortTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="pt_admin", phone_number="09190000001",
            password="Test@1234", role=User.Role.ADMIN, is_superuser=True,
        )
        self.template = WorkflowTemplate.objects.create(name="قالب تست جدول پرداخت", is_default=True)
        WorkflowStepTemplate.objects.create(template=self.template, order=1, title="صدور پیش‌فاکتور")
        WorkflowStepTemplate.objects.create(template=self.template, order=2, title="تایید پیش‌فاکتور")

        self.party_a = Party.objects.create(
            name="آلفا شرکت", phone_number="09190000011",
            entity_type=Party.EntityType.COMPANY, company_registration_number="8880001",
            is_client=True, is_partner=True,
        )
        self.party_b = Party.objects.create(
            name="بتا شرکت", phone_number="09190000012",
            entity_type=Party.EntityType.COMPANY, company_registration_number="8880002",
            is_client=True, is_partner=True,
        )
        self.service = Service.objects.create(name="خدمت تست جدول پرداخت")

        self.project_a, self.invoice_a, _ = create_project_from_technician_intake(
            created_by=self.admin_user, party_id=self.party_a.id,
            service_lines=[{"id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            material_lines=[], send_sms=False,
        )
        self.project_b, self.invoice_b, _ = create_project_from_technician_intake(
            created_by=self.admin_user, party_id=self.party_b.id,
            service_lines=[{"id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("2000000")}],
            material_lines=[], send_sms=False,
        )
        self.pay_a = create_customer_payment(
            invoice=self.invoice_a, method=Payment.Method.CARD_TO_CARD,
            amount_raw="100000", reference_number="REF-ALFA",
        )
        self.pay_b = create_customer_payment(
            invoice=self.invoice_b, method=Payment.Method.CARD_TO_CARD,
            amount_raw="900000", reference_number="REF-BETA",
        )

    def test_search_filters_by_project_name(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_q": "آلفا"})
        content = resp.content.decode("utf-8")
        self.assertIn(self.project_a.name, content)
        self.assertNotIn(self.project_b.name, content)

    def test_search_normalizes_persian_digits_in_invoice_number(self):
        client = Client()
        client.force_login(self.admin_user)
        persian_query = self.invoice_a.number.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        resp = client.get(reverse("finance:payments_table"), {"py_q": persian_query})
        self.assertIn(self.project_a.name, resp.content.decode("utf-8"))

    def test_search_no_match_shows_empty_state(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_q": "چیزی-که-نیست-XYZ"})
        self.assertIn("هنوز پرداختی ثبت نشده", resp.content.decode("utf-8"))

    def test_sort_by_amount_asc_then_desc(self):
        client = Client()
        client.force_login(self.admin_user)
        resp_asc = client.get(reverse("finance:payments_table"), {"py_sort": "amount", "py_dir": "asc"})
        content_asc = resp_asc.content.decode("utf-8")
        self.assertTrue(content_asc.find(self.project_a.name) < content_asc.find(self.project_b.name))

        resp_desc = client.get(reverse("finance:payments_table"), {"py_sort": "amount", "py_dir": "desc"})
        content_desc = resp_desc.content.decode("utf-8")
        self.assertTrue(content_desc.find(self.project_b.name) < content_desc.find(self.project_a.name))

    def test_unknown_sort_field_is_ignored_not_crashed(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_sort": "invoice__uuid__hacked"})
        self.assertEqual(resp.status_code, 200)

    def test_pagination_regression_with_search_and_sort_params_present(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_page_size": "1", "py_page": "2"})
        self.assertEqual(resp.status_code, 200)


class PaymentsTableAdvancedFilterTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="ptf_admin", phone_number="09190000101",
            password="Test@1234", role=User.Role.ADMIN, is_superuser=True,
        )
        self.template = WorkflowTemplate.objects.create(name="قالب تست فیلتر پرداخت", is_default=True)
        WorkflowStepTemplate.objects.create(template=self.template, order=1, title="صدور پیش‌فاکتور")
        WorkflowStepTemplate.objects.create(template=self.template, order=2, title="تایید پیش‌فاکتور")

        self.party = Party.objects.create(
            name="شرکت تست فیلتر", phone_number="09190000111",
            entity_type=Party.EntityType.COMPANY, company_registration_number="8880011",
            is_client=True, is_partner=True,
        )
        self.service = Service.objects.create(name="خدمت تست فیلتر پرداخت")
        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.admin_user, party_id=self.party.id,
            service_lines=[{"id": self.service.id, "qty": Decimal("1"), "unit_price": Decimal("5000000")}],
            material_lines=[], send_sms=False,
        )
        self.pay_card = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount_raw="100000", reference_number="REF-CARD",
        )
        self.pay_credit = create_customer_payment(
            invoice=self.invoice, method=Payment.Method.CREDIT,
            amount_raw="900000", note="اعتباری تست فیلتر",
        )

    def test_filter_by_method_select(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_f_method": "credit"})
        content = resp.content.decode("utf-8")
        self.assertNotIn("۱۰۰,۰۰۰", content)
        self.assertIn("۹۰۰,۰۰۰", content)

    def test_filter_by_amount_min(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_fmin_amount": "500000"})
        content = resp.content.decode("utf-8")
        self.assertIn("۹۰۰,۰۰۰", content)
        self.assertNotIn("۱۰۰,۰۰۰", content)

    def test_invalid_select_value_is_ignored_not_crashed(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_f_method": "this-is-not-a-real-method"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("کارت به کارت", resp.content.decode("utf-8"))

    def test_invalid_number_range_value_ignored(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {"py_fmin_amount": "not-a-number"})
        self.assertEqual(resp.status_code, 200)

    def test_reset_url_clears_filters_but_keeps_search(self):
        client = Client()
        client.force_login(self.admin_user)
        resp = client.get(reverse("finance:payments_table"), {
            "py_q": "test", "py_f_method": "credit", "py_sort": "amount", "py_dir": "desc",
        })
        self.assertEqual(resp.status_code, 200)
        reset_url = resp.context["reset_url"]
        self.assertIn("py_q=test", reset_url)
        self.assertNotIn("py_f_method", reset_url)
        self.assertNotIn("py_sort", reset_url)

