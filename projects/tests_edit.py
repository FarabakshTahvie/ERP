import json
from decimal import Decimal
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from core.models import Party, Specialty, Location
from catalog.models import Service, Item
from projects.models import Project, ProjectStage, WorkflowTemplate, WorkflowStepTemplate, StageApproval
from projects.services import create_project_from_technician_intake
from finance.models import Invoice, Payment
from finance.services import add_manual_invoice_line
from notifications.models import NotificationPolicy


class ProjectEditTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="tech_creator", phone_number="09120000081",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.other_tech = User.objects.create_user(
            username="tech_other", phone_number="09120000082",
            password="TechPassword123", role=User.Role.EMPLOYEE,
        )
        self.admin_user = User.objects.create_user(
            username="admin_user", phone_number="09120000083",
            password="AdminPassword123", role=User.Role.ADMIN,
        )
        self.sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.creator.specialties.add(self.sp_reception)
        self.other_tech.specialties.add(self.sp_reception)

        self.template = WorkflowTemplate.objects.create(name="قالب پیش‌فرض", is_default=True)
        self.step1 = WorkflowStepTemplate.objects.create(
            template=self.template, order=1, title="صدور پیش‌فاکتور",
        )
        self.step2 = WorkflowStepTemplate.objects.create(
            template=self.template, order=2, title="تایید پیش‌فاکتور", requires_payment_selection=True,
        )

        self.service1 = Service.objects.create(name="سرویس اول")
        self.service2 = Service.objects.create(name="سرویس دوم")
        self.item1 = Item.objects.create(name="متریال اول")

        NotificationPolicy.objects.get_or_create(
            notification_type="invoice_issued",
            defaults={"channel_policy": "sms_only", "fallback_after_minutes": 15},
        )

        self.party = Party.objects.create(name="کارفرمای اصلی", phone_number="09120000084", is_client=True)

        self.project, self.invoice, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=self.party.id,
            location_lat=Decimal("35.689200"),
            location_lng=Decimal("51.389000"),
            location_address="آدرس اولیه",
            service_lines=[{"id": self.service1.id, "qty": Decimal("2"), "unit_price": Decimal("500000")}],
            material_lines=[{"id": self.item1.id, "qty": Decimal("1"), "unit_price": Decimal("200000")}],
            send_sms=False,
        )

    def test_creator_can_edit_address_and_lines_rebuilds_invoice(self):
        client = Client()
        client.force_login(self.creator)

        ps = self.project.services.first()
        edit_data = {
            "latitude": "36.000000",
            "longitude": "52.000000",
            "address_text": "آدرس ویرایش‌شده",
            "services_json": json.dumps([{"pk": ps.pk, "id": self.service1.id, "qty": 3, "unit_price": 500000}]),
            "materials_json": json.dumps([]),
        }
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), edit_data)
        self.assertRedirects(resp, reverse("projects:staff_project_overview", args=[self.project.id]))

        self.project.refresh_from_db()
        self.assertEqual(self.project.location.address_text, "آدرس ویرایش‌شده")
        self.assertEqual(self.project.services.count(), 1)
        self.assertEqual(self.project.services.first().qty, Decimal("3"))
        self.assertEqual(self.project.extra_materials.count(), 0)

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, 1500000)
        self.assertEqual(self.invoice.address_snapshot, "آدرس ویرایش‌شده")

    def test_manual_invoice_line_preserved_after_edit(self):
        add_manual_invoice_line(self.invoice, title="کار اضافه دستی", amount=300000, actor=self.admin_user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, 1500000)  # 1200000 + 300000

        client = Client()
        client.force_login(self.creator)

        edit_data = {
            "address_text": "آدرس تست ردیف دستی",
            "services_json": json.dumps([{"id": self.service2.id, "qty": 1, "unit_price": 1000000}]),
            "materials_json": json.dumps([]),
        }
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), edit_data)
        self.assertRedirects(resp, reverse("projects:staff_project_overview", args=[self.project.id]))

        self.invoice.refresh_from_db()
        # 1000000 (سرویس جدید) + 300000 (دستی) = 1300000
        self.assertEqual(self.invoice.total_amount, 1300000)
        self.assertTrue(self.invoice.lines.filter(is_manual=True, title="کار اضافه دستی").exists())

    def test_service_description_preserved_with_pk(self):
        ps = self.project.services.first()
        ps.description = "توضیحات مهم خدمت"
        ps.save()

        client = Client()
        client.force_login(self.creator)

        edit_data = {
            "services_json": json.dumps([{"pk": ps.pk, "id": self.service1.id, "qty": 4, "unit_price": 500000}]),
            "materials_json": json.dumps([]),
        }
        client.post(reverse("projects:project_edit", args=[self.project.id]), edit_data)

        ps.refresh_from_db()
        self.assertEqual(ps.qty, Decimal("4"))
        self.assertEqual(ps.description, "توضیحات مهم خدمت")

    def test_prices_locked_after_payment_pending(self):
        Payment.objects.create(
            invoice=self.invoice, method=Payment.Method.CARD_TO_CARD, amount=500000, status=Payment.Status.PENDING,
        )

        client = Client()
        client.force_login(self.creator)

        # ارسال تغییر ردیف باید با خطا روبرو شود
        bad_edit = {
            "services_json": json.dumps([{"id": self.service1.id, "qty": 10, "unit_price": 500000}]),
        }
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), bad_edit)
        self.assertRedirects(resp, reverse("projects:project_edit", args=[self.project.id]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.services.first().qty, Decimal("2"))

        # اما ویرایش آدرس بدون ارسال ردیف‌ها موفق است و اسنپ‌شات آدرس فاکتور قفل می‌ماند
        good_edit = {
            "address_text": "آدرس جدید پس از قفل",
        }
        resp2 = client.post(reverse("projects:project_edit", args=[self.project.id]), good_edit)
        self.assertRedirects(resp2, reverse("projects:staff_project_overview", args=[self.project.id]))
        self.project.refresh_from_db()
        self.assertEqual(self.project.location.address_text, "آدرس جدید پس از قفل")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.address_snapshot, "آدرس اولیه")

    def test_prices_locked_after_stage2_done(self):
        stage2 = self.project.stages.get(order=2)
        stage2.status = ProjectStage.Status.DONE
        stage2.save()

        client = Client()
        client.force_login(self.creator)

        edit_data = {
            "services_json": json.dumps([{"id": self.service1.id, "qty": 5, "unit_price": 500000}]),
        }
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), edit_data)
        self.assertRedirects(resp, reverse("projects:project_edit", args=[self.project.id]))

    def test_permissions_other_tech_404_admin_allowed_completed_redirects(self):
        client = Client()
        client.force_login(self.other_tech)
        resp = client.get(reverse("projects:project_edit", args=[self.project.id]))
        self.assertEqual(resp.status_code, 404)

        client.force_login(self.admin_user)
        resp2 = client.get(reverse("projects:project_edit", args=[self.project.id]))
        self.assertEqual(resp2.status_code, 200)

        self.project.status = Project.Status.COMPLETED
        self.project.save()
        resp3 = client.get(reverse("projects:project_edit", args=[self.project.id]))
        self.assertRedirects(resp3, reverse("projects:staff_project_overview", args=[self.project.id]))

    def test_corrupted_or_missing_json_does_not_clear_lines(self):
        client = Client()
        client.force_login(self.creator)

        bad_json = {"services_json": "{bad"}
        resp = client.post(reverse("projects:project_edit", args=[self.project.id]), bad_json)
        self.assertRedirects(resp, reverse("projects:project_edit", args=[self.project.id]))
        self.assertEqual(self.project.services.count(), 1)

        # ارسال نکردن services_json
        no_json = {"address_text": "فقط آدرس جدید"}
        resp2 = client.post(reverse("projects:project_edit", args=[self.project.id]), no_json)
        self.assertRedirects(resp2, reverse("projects:staff_project_overview", args=[self.project.id]))
        self.assertEqual(self.project.services.count(), 1)

    def test_shared_location_creates_new_location_on_edit(self):
        shared_loc = self.project.location
        proj2 = Project.objects.create(
            name="پروژه دوم مشترک", partner=self.party, owner=self.party,
            location=shared_loc, workflow_template=self.template, created_by=self.creator,
        )

        client = Client()
        client.force_login(self.creator)

        edit_data = {"address_text": "آدرس اختصاصی پروژه اول"}
        client.post(reverse("projects:project_edit", args=[self.project.id]), edit_data)

        self.project.refresh_from_db()
        proj2.refresh_from_db()
        self.assertNotEqual(self.project.location_id, proj2.location_id)
        self.assertEqual(self.project.location.address_text, "آدرس اختصاصی پروژه اول")
        self.assertEqual(proj2.location.address_text, "آدرس اولیه")

    def test_intake_without_coordinates_creates_location_with_address(self):
        party2 = Party.objects.create(name="مشتری دوم", phone_number="09120000085", is_client=True)
        proj, _, _ = create_project_from_technician_intake(
            created_by=self.creator,
            party_id=party2.id,
            location_lat=None, location_lng=None,
            location_address="فقط متن آدرس بدون لوکیشن",
            service_lines=[], material_lines=[],
        )
        self.assertIsNotNone(proj.location)
        self.assertEqual(proj.location.address_text, "فقط متن آدرس بدون لوکیشن")
        self.assertIsNone(proj.location.latitude)

    def test_seen_total_guard_redirects_and_prevents_payment_creation(self):
        client = Client()
        # ایجاد کاربر مشتری متناظر با party (کاربر خودکار هنگام ساخت Party یا دستی)
        client_user = User.objects.filter(phone_number="09120000084").first()
        if not client_user:
            client_user = User.objects.create_user(
                username="client_user", phone_number="09120000084",
                password="ClientPassword123", role=User.Role.CLIENT,
            )
        self.party.user = client_user
        self.party.save()
        client.force_login(client_user)

        stage2 = self.project.stages.get(order=2)
        stage2.status = ProjectStage.Status.WAITING_APPROVAL
        stage2.save()
        approval = StageApproval.objects.create(stage=stage2, sent_to_party=self.party)

        post_data = {
            "action": "approve",
            "payment_method": "card_to_card",
            "seen_total": "999999",  # ناهمخوان با 1200000
            "comment": "تایید",
        }
        resp = client.post(reverse("projects:portal_stage_approval", args=[approval.id]), post_data)
        self.assertRedirects(resp, reverse("projects:portal_stage_approval", args=[approval.id]))
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 0)
