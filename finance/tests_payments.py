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
        self.tech_creator.specialties.add(self.sp_reception)
        self.other_tech.specialties.add(self.sp_reception)

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

        client.force_login(self.tech_creator)
        resp = client.get(reverse("finance:payment_detail", args=[pay.id]))
        self.assertEqual(resp.status_code, 200)

        post_resp = client.post(reverse("finance:payment_decide", args=[pay.id]), {"action": "approve"})
        self.assertRedirects(post_resp, reverse("finance:payment_detail", args=[pay.id]))
        pay.refresh_from_db()
        self.assertEqual(pay.status, Payment.Status.PENDING)

        client.force_login(self.other_tech)
        resp_other = client.get(reverse("finance:payment_detail", args=[pay.id]))
        self.assertEqual(resp_other.status_code, 404)

        client.force_login(self.admin_user)
        resp_admin = client.get(reverse("finance:payment_detail", args=[pay.id]))
        self.assertEqual(resp_admin.status_code, 200)

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
