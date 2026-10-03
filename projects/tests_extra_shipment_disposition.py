from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from core.models import Party, Specialty
from catalog.models import Item
from inventory.models import Warehouse, StockMovement
from inventory.services import receive_stock
from projects.models import Project, ProjectStage, StageKind, ExtraShipment
from projects.workflow_v2 import build_workflow_v2
from projects.services import create_project_from_technician_intake
from projects.ops import add_extra_shipment, resolve_extra_shipment_disposition


class ExtraShipmentDispositionTests(TestCase):
    def setUp(self):
        self.partner = Party.objects.create(name="شریک تست ارسال اضافه", is_partner=True, phone_number="09121160001")
        self.sp_intake, _ = Specialty.objects.get_or_create(name="پذیرش")
        self.sp_shipping, _ = Specialty.objects.get_or_create(name="راننده")
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")

        self.creator = User.objects.create_user(username="ex_creator", password="pw", role=User.Role.EMPLOYEE)
        self.creator.specialties.add(self.sp_intake)

        self.driver = User.objects.create_user(username="ex_driver", password="pw", role=User.Role.EMPLOYEE)
        self.driver.specialties.add(self.sp_shipping)

        self.accountant = User.objects.create_user(username="ex_accountant", password="pw", role=User.Role.EMPLOYEE)
        self.accountant.specialties.add(self.sp_accountant)

        self.manager = User.objects.create_user(username="ex_manager", password="pw", role=User.Role.ADMIN, is_superuser=True)
        self.other_tech = User.objects.create_user(username="ex_other", password="pw", role=User.Role.EMPLOYEE)

        self.wh = Warehouse.objects.create(name="انبار تست اضافه", is_default=True)
        self.item = Item.objects.create(name="کالای اضافه ارسال", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=self.item, warehouse=self.wh, qty=10, unit_cost=2000, received_at=timezone.now())

        build_workflow_v2(make_default=True)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=self.partner.id, visit_date=timezone.localdate(), issue_proforma=False,
        )
        self.ship_stage = self.project.stages.get(kind=StageKind.SHIPPING)
        self.ship_stage.status = ProjectStage.Status.IN_PROGRESS
        self.ship_stage.assigned_to = self.driver
        self.ship_stage.save()

        self.extra = add_extra_shipment(
            stage=self.ship_stage, item_id=self.item.id, qty_raw="3", note="قطعه اضافه برای احتیاط", actor=self.driver
        )

    def test_initial_disposition_is_pending_and_stock_unchanged(self):
        self.assertEqual(self.extra.disposition, ExtraShipment.Disposition.PENDING)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("10"))

    def test_resolve_consumed_reduces_stock_and_links_project(self):
        resolve_extra_shipment_disposition(
            extra=self.extra, disposition=ExtraShipment.Disposition.CONSUMED, actor=self.accountant
        )
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.disposition, ExtraShipment.Disposition.CONSUMED)
        self.assertEqual(self.extra.disposed_by, self.accountant)
        self.assertIsNotNone(self.extra.disposed_at)

        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("7"))

        movement = StockMovement.objects.filter(item=self.item, movement_type=StockMovement.MovementType.OUT).latest("created_at")
        self.assertEqual(movement.qty, Decimal("3"))
        self.assertEqual(movement.related_object, self.project)

    def test_resolve_returned_leaves_stock_unchanged(self):
        resolve_extra_shipment_disposition(
            extra=self.extra, disposition=ExtraShipment.Disposition.RETURNED, actor=self.manager
        )
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.disposition, ExtraShipment.Disposition.RETURNED)

        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("10"))

    def test_cannot_resolve_twice(self):
        resolve_extra_shipment_disposition(
            extra=self.extra, disposition=ExtraShipment.Disposition.RETURNED, actor=self.accountant
        )
        with self.assertRaises(ValueError):
            resolve_extra_shipment_disposition(
                extra=self.extra, disposition=ExtraShipment.Disposition.CONSUMED, actor=self.accountant
            )

    def test_unauthorized_user_cannot_resolve(self):
        with self.assertRaises(ValueError):
            resolve_extra_shipment_disposition(
                extra=self.extra, disposition=ExtraShipment.Disposition.CONSUMED, actor=self.creator
            )
        with self.assertRaises(ValueError):
            resolve_extra_shipment_disposition(
                extra=self.extra, disposition=ExtraShipment.Disposition.CONSUMED, actor=self.other_tech
            )

    def test_http_endpoint_resolution_for_accountant(self):
        client = Client()
        client.force_login(self.accountant)
        url = reverse("projects:extra_dispose", args=[self.extra.id])
        resp = client.post(url, {"disposition": "consumed"})
        self.assertEqual(resp.status_code, 302)
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.disposition, ExtraShipment.Disposition.CONSUMED)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("7"))
