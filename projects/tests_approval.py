from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate, StageApproval
from projects.services import (
    create_project_from_technician_intake, advance_stage, decide_stage_approval,
    create_project_stages_from_template,
)
from finance.models import Invoice, Payment
from finance.services import reject_payment
from utils.test_helpers import make_image_file


class StageApprovalTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr_appr", phone_number="09121110001",
            password="Password123", role=User.Role.ADMIN,
        )
        self.tech = User.objects.create_user(
            username="tech_appr", phone_number="09121110002",
            password="Password123", role=User.Role.EMPLOYEE,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.tech.specialties.add(self.sp_reception)

        self.party = Party.objects.create(name="کارفرمای تایید مراحل", phone_number="09121110003", is_client=True)
        self.client_user = User.objects.create_user(
            username="client_appr", phone_number="09121110003",
            password="Password123", role=User.Role.CLIENT,
        )
        self.client_user.party = self.party
        self.client_user.save()

        # ساخت پروژه با مراحل و قالب
        self.template = WorkflowTemplate.objects.create(name="قالب رد و پیشرفت", is_default=False)
        self.step1 = WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="پذیرش اولیه",
        )
        self.step2 = WorkflowStepTemplate.objects.create(
            template=self.template, order=2, title="طراحی نقشه",
        )
        self.step3 = WorkflowStepTemplate.objects.create(
            template=self.template, order=3, title="تایید طرح اولیه",
            approval_by=WorkflowStepTemplate.ApprovalBy.PARTNER,
            on_reject_go_to=self.step2,
        )
        self.step4 = WorkflowStepTemplate.objects.create(
            template=self.template, order=4, title="اجرای کانال",
        )

        self.service1 = Service.objects.create(name="خدمت تست تایید")
        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.tech,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("500000")}],
            material_lines=[],
            send_sms=False,
        )
        # جایگزینی مراحل پروژه با قالب اختصاصی تست
        self.project.workflow_template = self.template
        self.project.save()
        self.project.stages.all().delete()
        create_project_stages_from_template(self.project)

    # ۱. باگ مرحله‌ی رد‌شده
    def test_rejected_stage_reactivation_on_advance(self):
        stage1 = self.project.stages.get(order=1)
        stage2 = self.project.stages.get(order=2)
        stage3 = self.project.stages.get(order=3)
        stage4 = self.project.stages.get(order=4)

        # مرحله ۲ را به انجام می‌رسانیم
        stage2.status = ProjectStage.Status.IN_PROGRESS
        stage2.save()

        # به مرحله ۳ (تایید طرح) می‌رویم
        advance_stage(stage2, actor=self.tech, new_status=ProjectStage.Status.DONE, comment="تکمیل طراحی")
        stage3.refresh_from_db()
        self.assertEqual(stage3.status, ProjectStage.Status.WAITING_APPROVAL)

        approval = stage3.approvals.filter(decision=StageApproval.Decision.PENDING).first()
        self.assertIsNotNone(approval)

        # رد مرحله ۳ (تایید طرح)
        decide_stage_approval(approval, actor=self.client_user, decision=StageApproval.Decision.REJECTED, comment="طرح اصلاح شود")
        stage3.refresh_from_db()
        self.assertEqual(stage3.status, ProjectStage.Status.REJECTED)

        # تکنسین مرحله ۲ را دوباره انجام داده و پیش می‌برد
        stage2.status = ProjectStage.Status.IN_PROGRESS
        stage2.save()
        advance_stage(stage2, actor=self.tech, new_status=ProjectStage.Status.DONE, comment="اصلاح طراحی")

        # _activate_next_stage مرحله ۳ رد‌شده را فعال می‌کند (چون template دارای PARTNER approval است، به WAITING_APPROVAL می‌رود)
        stage3.refresh_from_db()
        self.assertEqual(stage3.status, ProjectStage.Status.WAITING_APPROVAL)
        self.assertTrue(stage3.approvals.filter(decision=StageApproval.Decision.PENDING).exists())

        # مرحله ۴ باید PENDING بماند
        stage4.refresh_from_db()
        self.assertEqual(stage4.status, ProjectStage.Status.PENDING)

    # ۲. دوبار تایید
    def test_double_approval_prevention(self):
        stage3 = self.project.stages.get(order=3)
        stage3.status = ProjectStage.Status.WAITING_APPROVAL
        stage3.save()
        approval = StageApproval.objects.create(stage=stage3, sent_to_party=self.party)

        client = Client()
        client.force_login(self.client_user)

        # POST اول
        resp1 = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), {
            "action": "approve", "comment": "تایید اولیه",
        })
        self.assertEqual(resp1.status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, StageApproval.Decision.APPROVED)

        # POST دوم روی همان تایید
        resp2 = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), {
            "action": "approve", "comment": "تایید دوباره",
        })
        # رندر صفحه یا ریدایرکت با پیام قبلاً بررسی شده
        self.assertEqual(resp2.status_code, 200)

    # ۳. بازگشت کامل هنگام خطای پرداخت
    def test_payment_failure_rolls_back_approval(self):
        stage3 = self.project.stages.get(order=3)
        stage3.status = ProjectStage.Status.WAITING_APPROVAL
        stage3.step_template.requires_payment_selection = True
        stage3.step_template.save()
        stage3.save()
        approval = StageApproval.objects.create(stage=stage3, sent_to_party=self.party)

        client = Client()
        client.force_login(self.client_user)

        # ارسال تایید با کارت‌به‌کارت بدون تصویر و بدون پیگیری
        resp = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), {
            "action": "approve",
            "payment_method": "card_to_card",
            "payment_amount": "200000",
            "seen_total": str(int(self.invoice.total_amount)),
        })
        self.assertEqual(resp.status_code, 200)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, StageApproval.Decision.PENDING)
        self.assertFalse(Payment.objects.filter(claimed_amount=200000).exists())

    # ۴. رد بدون پرداخت
    def test_reject_action_without_payment_fields(self):
        stage3 = self.project.stages.get(order=3)
        stage3.status = ProjectStage.Status.WAITING_APPROVAL
        stage3.save()
        approval = StageApproval.objects.create(stage=stage3, sent_to_party=self.party)

        client = Client()
        client.force_login(self.client_user)

        resp = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), {
            "action": "reject",
            "comment": "نیاز به بازبینی کامل دارد",
        })
        self.assertEqual(resp.status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.decision, StageApproval.Decision.REJECTED)

    # ۵. بنر خانه
    def test_client_home_approval_banner(self):
        client = Client()
        client.force_login(self.client_user)

        # پیش‌فرض create_project_from_technician_intake مرحله پیش‌فاکتور را در وضعیت WAITING_APPROVAL قرار می‌دهد
        # برای تست حالت «بدون مرحله معطل»، وضعیت تمام مراحل را به IN_PROGRESS یا PENDING تغییر می‌دهیم:
        self.project.stages.update(status=ProjectStage.Status.IN_PROGRESS)

        # بدون مرحله معطل: بنر نیست
        resp1 = client.get(reverse("home"))
        self.assertNotContains(resp1, "منتظر تایید شماست")

        # با مرحله معطل: بنر ظاهر می‌شود
        stage3 = self.project.stages.get(order=3)
        stage3.status = ProjectStage.Status.WAITING_APPROVAL
        stage3.client_visible = True
        stage3.save()
        StageApproval.objects.create(stage=stage3, sent_to_party=self.party)

        resp2 = client.get(reverse("home"))
        self.assertContains(resp2, "منتظر تایید شماست")
        self.assertContains(resp2, reverse("projects:portal_stage_approval", args=[stage3.approvals.first().id]))

    # ۶. فاکتور با دلیل رد
    def test_invoice_shows_rejection_reason(self):
        pay = Payment.objects.create(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount=200000, claimed_amount=200000, reference_number="REF-X",
        )
        reject_payment(pay, rejected_by=self.manager, reason="تصویر ناخواناست")

        client = Client()
        client.force_login(self.client_user)
        resp = client.get(reverse("finance:portal_invoice_detail", args=[self.invoice.uuid]))
        self.assertContains(resp, "دلیل رد: تصویر ناخواناست")

    # ۷. صفحه‌ی مراحل
    def test_project_progress_action_links_and_timeline(self):
        stage3 = self.project.stages.get(order=3)
        stage3.status = ProjectStage.Status.WAITING_APPROVAL
        stage3.client_visible = True
        stage3.save()
        approval = StageApproval.objects.create(stage=stage3, sent_to_party=self.party)

        client = Client()
        client.force_login(self.client_user)
        resp = client.get(reverse("projects:portal_project_progress", args=[self.project.id]))
        self.assertContains(resp, "fb-timeline")
        self.assertContains(resp, reverse("projects:portal_stage_approval", args=[approval.id]))
