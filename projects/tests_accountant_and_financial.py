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
from projects.workflow_v3 import build_workflow_v3
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

        build_workflow_v3(make_default=True)
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

        build_workflow_v3(make_default=True)
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



