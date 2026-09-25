from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Specialty, Party, Location
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate
from projects.services import create_project_stages_from_template, claim_stage, transfer_stage
from catalog.models import Service
from finance.models import Invoice, Payment
from finance.forms import PaymentInlineForm


class TechnicianTasksTests(TestCase):
    def setUp(self):
        self.sp_cnc, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
        self.sp_assembler, _ = Specialty.objects.get_or_create(name="مونتاژکار")

        self.tech1 = User.objects.create_user(
            username="tech1", phone_number="09120000081",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech1.specialties.add(self.sp_cnc)

        self.tech2 = User.objects.create_user(
            username="tech2", phone_number="09120000082",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech2.specialties.add(self.sp_cnc)

        self.tech_other = User.objects.create_user(
            username="tech_other", phone_number="09120000083",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.tech_other.specialties.add(self.sp_assembler)

        self.partner = Party.objects.create(name="همکار", is_partner=True, national_code="1111111111")
        self.template = WorkflowTemplate.objects.create(name="قالب تست", is_default=True)
        self.step = WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="جی‌کدگیری",
            responsible_specialty=self.sp_cnc,
        )
        self.project = Project.objects.create(
            name="پروژه تست کارهای من", partner=self.partner,
            workflow_template=self.template,
        )
        self.stages = create_project_stages_from_template(self.project)
        self.stage = self.stages[0]

    def test_my_tasks_list_shows_assigned_and_pool_tasks(self):
        self.stage.candidate_users.add(self.tech1)
        client = Client()
        client.force_login(self.tech1)
        resp = client.get(reverse("projects:dashboard_claimable_table"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("پروژه تست کارهای من", resp.content.decode("utf-8"))

    def test_claim_stage(self):
        self.stage.candidate_users.add(self.tech1)
        client = Client()
        client.force_login(self.tech1)
        resp = client.post(reverse("projects:my_task_claim", args=[self.stage.id]))
        self.assertRedirects(resp, reverse("projects:my_task_detail", args=[self.stage.id]))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.tech1)

    def test_transfer_stage_to_same_specialty(self):
        self.stage.assigned_to = self.tech1
        self.stage.save()

        client = Client()
        client.force_login(self.tech1)
        resp = client.post(reverse("projects:my_task_transfer", args=[self.stage.id]), {
            "target_user": self.tech2.id,
            "comment": "انتقال به همکار",
        })
        self.assertRedirects(resp, reverse("home"))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.assigned_to, self.tech2)

    def test_transfer_stage_to_different_specialty_fails(self):
        self.stage.assigned_to = self.tech1
        self.stage.save()

        with self.assertRaises(ValueError):
            transfer_stage(self.stage, from_user=self.tech1, to_user=self.tech_other, comment="خطا")


class PaymentFormValidationTests(TestCase):
    def test_cheque_and_receipt_method_requires_file(self):
        form = PaymentInlineForm(data={
            "method": Payment.Method.CHEQUE,
            "amount": 100000,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("برای رسید واریز و چک، آپلود تصویر رسید/چک الزامی است.", str(form.errors))


class TechnicianPaymentCounterTests(TestCase):
    def setUp(self):
        self.tech_reception = User.objects.create_user(
            username="tech_rec_badge", phone_number="09122220001",
            password="Password123", role=User.Role.EMPLOYEE,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.tech_reception.specialties.add(self.sp_reception)

        self.tech_other = User.objects.create_user(
            username="tech_other_badge", phone_number="09122220002",
            password="Password123", role=User.Role.EMPLOYEE,
        )

        self.manager = User.objects.create_user(
            username="mgr_badge", phone_number="09122220003",
            password="Password123", role=User.Role.ADMIN,
        )

        self.party = Party.objects.create(name="کارفرما تست شمارنده", phone_number="09122220004", is_client=True)
        self.client_user = User.objects.create_user(
            username="client_badge", phone_number="09122220004",
            password="Password123", role=User.Role.CLIENT,
        )
        self.client_user.party = self.party
        self.client_user.save()

        self.service1 = Service.objects.create(name="خدمت تست بج")
        from decimal import Decimal
        from projects.services import create_project_from_technician_intake
        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.tech_reception,
            party_id=self.party.id,
            service_lines=[{"id": self.service1.id, "qty": Decimal("1"), "unit_price": Decimal("1000000")}],
            material_lines=[],
            send_sms=False,
        )

        # ساخت ۲ پرداخت در انتظار برای این فاکتور
        Payment.objects.create(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount=100000, claimed_amount=100000, reference_number="REF-B1", status=Payment.Status.PENDING,
        )
        Payment.objects.create(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
            amount=200000, claimed_amount=200000, reference_number="REF-B2", status=Payment.Status.PENDING,
        )

    # ۸. تکنسین «پذیرش» با ۲ پرداخت در انتظار بج ۲ را می‌بیند و هشدار زرد جدا نیست
    def test_technician_badge_and_no_separate_alert(self):
        client = Client()
        client.force_login(self.tech_reception)
        resp = client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn("پرداخت‌ها", content)
        self.assertIn("fb-badge-warning", content)
        self.assertIn("۲", content)
        self.assertNotIn("پرداخت در انتظار تایید شماست", content)

    # ۹. مدیر بج را در منوی بالا می‌بیند، مشتری متغیر و لینک را ندارد
    def test_manager_and_client_nav_counter(self):
        client = Client()

        # مدیر
        client.force_login(self.manager)
        resp_mgr = client.get(reverse("home"))
        content_mgr = resp_mgr.content.decode("utf-8")
        self.assertIn(reverse("finance:payments_review"), content_mgr)
        self.assertIn("fb-badge-warning", content_mgr)

        # مشتری
        client.force_login(self.client_user)
        resp_cli = client.get(reverse("home"))
        content_cli = resp_cli.content.decode("utf-8")
        self.assertNotIn(reverse("finance:payments_review"), content_cli)
        self.assertNotIn("pending_payments_nav_count", resp_cli.context)
