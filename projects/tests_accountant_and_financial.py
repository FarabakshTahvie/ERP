from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Service, Item
from inventory.models import Warehouse
from inventory.services import receive_stock, user_can_manage_inventory
from projects.models import Project, ProjectStage, StageKind
from projects.workflow_v2 import build_workflow_v2
from projects.services import (
    create_project_from_technician_intake, advance_stage,
    user_can_create_projects, user_is_accountant,
)
from projects.proforma import parse_service_rows, save_proforma, issue_proforma
from projects import ops


class AccountantSpecialtyAccessTests(TestCase):
    def setUp(self):
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.accountant = User.objects.create_user(username="acc_1", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)

    def test_accountant_can_create_projects_and_manage_inventory(self):
        self.assertTrue(user_can_create_projects(self.accountant))
        self.assertTrue(user_can_manage_inventory(self.accountant))
        self.assertTrue(user_is_accountant(self.accountant))

    def test_plain_employee_is_not_accountant(self):
        plain = User.objects.create_user(username="plain_1", password="pw", role=User.Role.EMPLOYEE)
        self.assertFalse(user_is_accountant(plain))
        self.assertFalse(user_can_manage_inventory(plain))


class FinalReviewThreePersonAccessTests(TestCase):
    """بازبینی نهایی باید فقط برای مدیر، حسابدار و ثبت‌کننده در دسترس باشد."""

    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست حسابدار", is_partner=True, phone_number="09121150001")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.creator = User.objects.create_user(username="fr_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)
        self.accountant = User.objects.create_user(username="fr_accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.manager = User.objects.create_user(username="fr_manager", password="pw", role=User.Role.ADMIN, is_superuser=True)
        self.other_tech = User.objects.create_user(username="fr_other", password="pw", role=User.Role.EMPLOYEE)

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )
        self.review_stage = self.project.stages.get(kind=StageKind.FINAL_REVIEW)
        self.review_stage.status = ProjectStage.Status.IN_PROGRESS
        self.review_stage.save()

    def test_access_matrix(self):
        url = reverse("projects:final_review", args=[self.project.id])
        client = Client()
        for user, expected in (
            (self.manager, 200), (self.accountant, 200), (self.creator, 404), (self.other_tech, 404),
        ):
            client.force_login(user)
            resp = client.get(url)
            self.assertEqual(resp.status_code, expected, msg=f"{user.username} باید {expected} بگیرد")

    def test_accountant_can_approve_final_review(self):
        client = Client()
        client.force_login(self.accountant)
        resp = client.post(reverse("projects:final_review", args=[self.project.id]), {"comment": "تایید حسابدار"})
        self.assertEqual(resp.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.COMPLETED)

    def test_other_tech_cannot_approve_final_review(self):
        client = Client()
        client.force_login(self.other_tech)
        resp = client.post(reverse("projects:final_review", args=[self.project.id]), {"comment": "تایید غیرمجاز"})
        self.assertEqual(resp.status_code, 404)
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.status, Project.Status.COMPLETED)


class FinalReviewManualConsumeTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست مصرف", is_partner=True, phone_number="09121150002")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.creator = User.objects.create_user(username="mc_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)
        self.accountant = User.objects.create_user(username="mc_accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.wh = Warehouse.objects.create(name="انبار تست مصرف", is_default=True)
        self.item = Item.objects.create(name="کالای تست مصرف نهایی", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=1000, received_at=timezone.now())

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )

    def test_consume_from_final_review_reduces_stock_and_links_project(self):
        client = Client()
        client.force_login(self.accountant)
        url = reverse("projects:final_review_consume", args=[self.project.id])
        resp = client.post(url, {"item_id": self.item.id, "kind": "consume", "qty": "3", "notes": "مصرف تست نهایی"})
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("7"))
        from inventory.models import StockMovement
        from django.contrib.contenttypes.models import ContentType
        movement = StockMovement.objects.filter(item=self.item, movement_type=StockMovement.MovementType.OUT).latest("created_at")
        self.assertEqual(movement.related_content_type, ContentType.objects.get_for_model(Project))
        self.assertEqual(movement.related_object_id, self.project.id)

    def test_unauthorized_user_cannot_consume(self):
        other = User.objects.create_user(username="mc_other", password="pw", role=User.Role.EMPLOYEE)
        client = Client()
        client.force_login(other)
        resp = client.post(reverse("projects:final_review_consume", args=[self.project.id]),
                            {"item_id": self.item.id, "kind": "consume", "qty": "1", "notes": "تست"})
        self.assertEqual(resp.status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("10"))

    def test_final_review_page_renders_manual_consume_form_for_accountant_only(self):
        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("projects:final_review", args=[self.project.id]))
        self.assertContains(resp, "مصرف کالای دیگر")

        plain = User.objects.create_user(username="mc_plain", password="pw", role=User.Role.EMPLOYEE)
        self.project.created_by = plain
        self.project.save()
        client.force_login(plain)
        resp2 = client.get(reverse("projects:final_review", args=[self.project.id]))
        self.assertEqual(resp2.status_code, 404)


class FinalReviewPaymentHistoryAndProfitLabelTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست پرداخت نهایی", is_partner=True, phone_number="09121150003")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.creator = User.objects.create_user(username="ph_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)
        self.accountant = User.objects.create_user(username="ph_accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.service = Service.objects.create(name="خدمت تست پرداخت نهایی")

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )
        st1 = self.project.stages.get(order=1)
        st1.assigned_to = self.creator
        st1.save()
        advance_stage(st1, actor=self.creator, new_status=ProjectStage.Status.DONE, comment="بازدید شد.")
        rows = parse_service_rows('[{"service_id": %d, "qty": "1", "unit_price": "1000000", "materials": []}]' % self.service.id)
        save_proforma(project=self.project, actor=self.accountant, service_rows=rows)
        self.invoice, _ = issue_proforma(project=self.project, actor=self.accountant)

        from finance.models import Payment
        Payment.objects.create(invoice=self.invoice, method=Payment.Method.CARD_TO_CARD,
                               amount=200000, claimed_amount=200000, reference_number="REF-FR-1",
                               status=Payment.Status.APPROVED)

    def test_payment_history_and_remaining_amount_render_correctly(self):
        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("projects:final_review", args=[self.project.id]))
        content = resp.content.decode("utf-8")
        self.assertIn("گزارش کامل پرداخت‌ها", content)
        # مانده باید رندر شده باشد نه خالی (رگرسیون باگ invoice.balance_due)
        remaining_fa = format(int(self.invoice.remaining_amount), ",").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
        self.assertIn(remaining_fa, content)

    def test_shortage_and_surplus_profit_loss_labels(self):
        from projects.ops import ensure_install_lines, set_install_line
        from projects.models import InstallLine
        # ساخت متریال برای خدمت تا InstallLine از نوع MATERIAL ایجاد شود
        mat_item = Item.objects.create(name="کالای تست نصب", item_type=Item.ItemType.MATERIAL, moving_average_cost=Decimal("1000"))
        ps = self.project.services.first()
        from projects.models import ProjectServiceMaterial
        ProjectServiceMaterial.objects.create(
            service_line=ps, item=mat_item, qty=Decimal("1"),
            cost_snapshot=Decimal("1000"), margin_percent=Decimal("20")
        )
        install_stage = self.project.stages.get(kind=StageKind.INSTALL)
        install_stage.status = ProjectStage.Status.IN_PROGRESS
        install_stage.assigned_to = self.creator
        install_stage.save()
        ensure_install_lines(install_stage)
        mat_line = install_stage.install_lines.get(kind=InstallLine.Kind.MATERIAL)
        # delta_qty = actual - planned. برای کسری (بیشتر از planned)، actual را 2 می‌دهیم تا delta_qty = +1 شود
        set_install_line(line=mat_line, status="ok", actual_qty_raw="2", reason="", actor=self.creator)

        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("projects:final_review", args=[self.project.id]))
        # قانون طلایی: عدم قضاوت سود و زیان
        self.assertNotContains(resp, ">زیان<")
        self.assertContains(resp, "بیشتر از پیش‌فاکتور")


class AccountantHomeLinksToAccountingCenterTests(TestCase):
    def setUp(self):
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.accountant = User.objects.create_user(username="dash_acc", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)
        self.manager = User.objects.create_superuser(username="dash_mgr", password="pw")
        self.client_user = User.objects.create_user(username="dash_client", password="pw", role=User.Role.CLIENT)

    def test_dashboard_renders_accounting_center_link_for_accountant_and_manager(self):
        client = Client()
        client.force_login(self.accountant)
        resp = client.get(reverse("home"))
        self.assertContains(resp, reverse("finance:accounting_overview"))
        self.assertNotContains(resp, "برآورد خام سود")
        self.assertContains(resp, "flex flex-wrap items-center gap-2")

        client.force_login(self.manager)
        resp_mgr = client.get(reverse("home"))
        self.assertContains(resp_mgr, reverse("finance:accounting_overview"))

        client.force_login(self.client_user)
        resp_cli = client.get(reverse("home"))
        self.assertNotContains(resp_cli, reverse("finance:accounting_overview"))

    def test_input_css_contains_overflow_wrap(self):
        from django.conf import settings
        import os
        css_path = os.path.join(settings.BASE_DIR, "static", "src", "input.css")
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".fb-stat-value", content)
        self.assertIn("overflow-wrap: anywhere", content)
