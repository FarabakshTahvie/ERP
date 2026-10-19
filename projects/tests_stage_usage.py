from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, Service
from core.models import Party
from finance import accounting
from inventory.models import Warehouse
from inventory.services import consume_stock, item_structure_locked, receive_stock
from projects.models import FileGroup, ProjectService, ProjectServiceMaterial, ProjectStage, StageKind, StageUsage
from projects.services import create_project_from_technician_intake, transfer_stage
from projects.usage import parse_usage_qty, set_usage, stage_has_progress, usage_context
from projects.workflow_v3 import build_workflow_v3


class UsageBase(TestCase):
    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        partner = Party.objects.create(name="شریک مصرف", is_partner=True, phone_number="09125550404")
        mk = User.objects.create_user
        self.creator = mk(username="us_creator", password="pw", role=User.Role.EMPLOYEE)
        self.worker = mk(username="us_worker", password="pw", role=User.Role.EMPLOYEE)
        self.peer = mk(username="us_peer", password="pw", role=User.Role.EMPLOYEE)
        self.stranger = mk(username="us_stranger", password="pw", role=User.Role.EMPLOYEE)
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.creator, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.item = Item.objects.create(name="ورق گالوانیزه", item_type=Item.ItemType.MATERIAL,
                                        unit=Item.Unit.SQUARE_METER)
        self.other = Item.objects.create(name="پیچ", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        line = ProjectService.objects.create(project=self.project, service=Service.objects.create(name="خدمت مصرف"),
                                             qty=1, unit_price=1000)
        ProjectServiceMaterial.objects.create(service_line=line, item=self.item, qty=Decimal("10"))
        self.cutting = self.open_stage(StageKind.CUTTING)
        self.assembly = self.open_stage(StageKind.ASSEMBLY)
        self.client.force_login(self.worker)

    def open_stage(self, kind):
        stage = self.project.stages.get(kind=kind)
        stage.status = ProjectStage.Status.IN_PROGRESS
        stage.assigned_to = self.worker
        stage.save()
        return stage

    def put(self, stage, item, qty, actor=None):
        return set_usage(stage=stage, item_id=item.id, qty_raw=qty, actor=actor or self.worker)


class UsageParseTests(TestCase):
    def test_decimals_and_persian_digits_are_accepted(self):
        self.assertEqual(parse_usage_qty("4.5"), Decimal("4.5"))
        self.assertEqual(parse_usage_qty("۴٫۵"), Decimal("4.5"))
        self.assertEqual(parse_usage_qty("۱۲"), Decimal("12"))

    def test_letters_negative_and_garbage_are_rejected(self):
        for bad in ("abc", "4a", "-1", "1e3", "4.5.6", "٪"):
            with self.assertRaises(ValueError, msg=bad):
                parse_usage_qty(bad)

    def test_empty_zero_mean_no_usage_and_limits(self):
        self.assertIsNone(parse_usage_qty(""))
        self.assertIsNone(parse_usage_qty(None))
        self.assertIsNone(parse_usage_qty("0"))
        with self.assertRaises(ValueError):
            parse_usage_qty("0.00001")
        with self.assertRaises(ValueError):
            parse_usage_qty("99999999")


class UsageServiceTests(UsageBase):
    def test_decimal_is_saved_and_replaced(self):
        self.assertEqual(self.put(self.cutting, self.item, "۴٫۵"), {"qty": "4.5", "removed": False, "short": "4.5"})
        self.put(self.cutting, self.item, "6")
        usage = StageUsage.objects.get()
        self.assertEqual((usage.qty, usage.updated_by), (Decimal("6"), self.worker))

    def test_empty_or_zero_removes_row(self):
        self.put(self.cutting, self.item, "3")
        self.assertEqual(self.put(self.cutting, self.item, ""), {"qty": "", "removed": True, "short": ""})
        self.assertFalse(StageUsage.objects.exists())
        self.put(self.cutting, self.item, "3")
        self.put(self.cutting, self.item, "0")
        self.assertFalse(StageUsage.objects.exists())

    def test_every_stage_has_its_own_usage(self):
        self.put(self.cutting, self.item, "4")
        self.assertEqual(usage_context(self.worker, self.assembly)["rows"][0]["qty"], "")
        self.put(self.assembly, self.item, "1.5")
        self.assertEqual(StageUsage.objects.count(), 2)
        self.assertEqual(usage_context(self.worker, self.cutting)["rows"][0]["qty"], "4")

    def test_permissions_and_stage_rules(self):
        with self.assertRaises(ValueError):
            self.put(self.cutting, self.item, "1", actor=self.stranger)
        with self.assertRaises(ValueError):
            self.put(self.project.stages.get(kind=StageKind.VISIT), self.item, "1")
        shipping = self.project.stages.get(kind=StageKind.SHIPPING)        # هنوز در انتظار
        with self.assertRaises(ValueError):
            self.put(shipping, self.item, "1")
        with self.assertRaises(ValueError):
            set_usage(stage=self.cutting, item_id="x", qty_raw="1", actor=self.worker)
        Item.objects.filter(pk=self.other.pk).update(is_active=False)
        with self.assertRaises(ValueError):
            self.put(self.cutting, self.other, "1")

    def test_done_stage_is_editable_by_creator_not_by_worker(self):
        ProjectStage.objects.filter(pk=self.cutting.pk).update(status=ProjectStage.Status.DONE)
        with self.assertRaises(ValueError):
            self.put(self.cutting, self.item, "1")
        self.put(self.cutting, self.item, "1", actor=self.creator)
        self.assertEqual(StageUsage.objects.count(), 1)





class UsageTransferLockTests(UsageBase):
    def test_transfer_blocked_after_first_usage_or_group_tick(self):
        self.peer.specialties.add(self.cutting.step_template.responsible_specialty)
        self.put(self.cutting, self.item, "1")
        with self.assertRaises(ValueError) as cm:
            transfer_stage(self.cutting, from_user=self.worker, to_user=self.peer, comment="")
        self.assertIn("واگذار", str(cm.exception))
        self.put(self.cutting, self.item, "")
        self.assertFalse(stage_has_progress(self.cutting))
        FileGroup.objects.create(project=self.project, stage=self.project.stages.get(kind=StageKind.GCODE),
                                 title="طبقه اول", cut_done=True)
        self.assertTrue(stage_has_progress(self.cutting))
        with self.assertRaises(ValueError):
            transfer_stage(self.cutting, from_user=self.worker, to_user=self.peer, comment="")
        FileGroup.objects.update(cut_done=False)
        transfer_stage(self.cutting, from_user=self.worker, to_user=self.peer, comment="")
        self.cutting.refresh_from_db()
        self.assertEqual(self.cutting.assigned_to_id, self.peer.id)




class UsageReconTests(UsageBase):
    def test_reconciliation_shows_only_used_items_with_per_stage_breakdown(self):
        self.assertEqual(accounting.project_reconciliation(self.project), [])
        self.put(self.cutting, self.item, "4.5")
        self.put(self.assembly, self.item, "2")
        rows = accounting.project_reconciliation(self.project)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["basis"], rows[0]["expected"], rows[0]["planned"]),
                         ("usage", Decimal("6.5"), Decimal("10")))
        self.assertEqual([b["qty"] for b in rows[0]["by_stage"]], [Decimal("4.5"), Decimal("2")])

    def test_deducted_without_usage_is_manual_basis(self):
        wh = Warehouse.objects.create(name="انبار مصرف", is_default=True)
        receive_stock(item=self.other, warehouse=wh, qty=Decimal("10"), unit_cost=Decimal("100"),
                      received_at=timezone.now())
        consume_stock(item=self.other, qty=Decimal("3"), user=self.creator, notes="x", related_object=self.project)
        r = accounting.project_reconciliation(self.project)[0]
        self.assertEqual((r["basis"], r["expected"], r["status"]), ("manual", Decimal("3"), "ok"))



