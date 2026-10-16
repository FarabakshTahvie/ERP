import shutil
import tempfile
from datetime import date

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Item
from core.models import Party
from finance.models import AccountingEvent
from inventory.models import Warehouse
from inventory.services import consume_stock, receive_stock
from projects.models import ProjectFile, StageEvent, StageKind
from projects.services import create_project_from_technician_intake, suspend_stage
from projects.workflow_v3 import build_workflow_v3


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class NoneUserPagesTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        Party.objects.filter(is_internal=True).first() or Party.objects.create(name="شرکت ما", is_internal=True)
        build_workflow_v3(make_default=True)
        self.manager = User.objects.create_user(username="np_mgr", password="pw", role=User.Role.ADMIN)
        partner = Party.objects.create(name="شریک بدون کاربر", is_partner=True, phone_number="09125550777")
        self.project, _, _ = create_project_from_technician_intake(
            created_by=self.manager, party_id=partner.id, visit_date=date(2026, 10, 11), issue_proforma=False)
        self.stage = self.project.stages.get(kind=StageKind.VISIT)
        StageEvent.objects.create(stage=self.stage, actor=None, from_status="in_progress",
                                  to_status="in_progress", comment="رویداد سیستمی")
        ProjectFile.objects.create(stage=self.stage, file=SimpleUploadedFile("a.pdf", b"%PDF-1.4 x"), kind="pdf",
                                   original_name="a.pdf", uploaded_by=None, is_attachment=True)
        AccountingEvent.objects.create(project=self.project, kind="cost", text="رویداد سیستمی", actor=None)
        wh = Warehouse.objects.create(name="انبار بدون کاربر", is_default=True)
        item = Item.objects.create(name="کالای بدون کاربر", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)
        receive_stock(item=item, warehouse=wh, qty=5, unit_cost=100, received_at=timezone.now())
        consume_stock(item=item, qty=1, user=None, related_object=self.project)
        suspend_stage(self.stage, actor=self.manager, comment="تعلیق")

    def test_pages_render_when_actor_or_uploader_is_missing(self):
        c = Client()
        c.force_login(self.manager)
        pages = (("projects:staff_project_overview", [self.project.id]),
                 ("projects:final_review", [self.project.id]),
                 ("finance:accounting_project", [self.project.id]),
                 ("dashboard:held_detail", [self.project.id]),
                 ("dashboard:assign_stage", [self.stage.id]))
        for name, args in pages:
            with self.subTest(name):
                self.assertEqual(c.get(reverse(name, args=args)).status_code, 200)
