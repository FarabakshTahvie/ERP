import jdatetime
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Specialty, Party
from catalog.models import Item
from inventory.models import Warehouse, Purchase, PurchaseLine
from finance.models import Invoice, Payment
from projects.models import Project, ProjectCost

User = get_user_model()


class ReportsAndExportersTests(TestCase):
    def setUp(self):
        self.sp_accountant, _ = Specialty.objects.get_or_create(name="حسابدار")
        self.accountant_user = User.objects.create_user(
            username="acc_user", phone_number="09300000021",
            password="Test@1234", role=User.Role.EMPLOYEE,
        )
        self.accountant_user.specialties.add(self.sp_accountant)

        self.partner = Party.objects.create(name="شریک", is_partner=True, entity_type=Party.EntityType.INDIVIDUAL, national_code="1234567890")
        self.client_party = Party.objects.create(name="مشتری", is_client=True, entity_type=Party.EntityType.INDIVIDUAL, national_code="0987654321")
        self.warehouse = Warehouse.objects.create(name="انبار", is_default=True)
        self.item = Item.objects.create(name="کالا", item_type=Item.ItemType.MATERIAL, unit=Item.Unit.PIECE)

        # ایجاد پروژه
        self.project = Project.objects.create(
            name="پروژه گزارش", partner=self.partner, owner=self.client_party, status=Project.Status.IN_PROGRESS
        )

        # فاکتور نهایی به مبلغ ۵۰۰,۰۰۰ تومان
        self.invoice = Invoice.objects.create(
            number="INV-12345",
            billed_party=self.client_party, project=self.project, document_type=Invoice.DocumentType.FINAL,
            status=Invoice.Status.SENT, total_amount=500000, issue_date=jdatetime.date(1405, 5, 10).togregorian()
        )

        from django.utils import timezone
        import datetime
        self.cost = ProjectCost.objects.create(
            project=self.project, kind=ProjectCost.Kind.TRANSPORT, amount=50000,
            title="حمل تستی"
        )
        self.cost.created_at = timezone.make_aware(datetime.datetime.combine(jdatetime.date(1405, 5, 12).togregorian(), datetime.time(12, 0)))
        self.cost.save()

    def test_generate_periodic_financial_report(self):
        # همچنین تعلیق پروژه باید درآمد و هزینه‌ی آن را از گزارش دوره‌ای حذف کند
        from projects.services import suspend_stage
        from projects.models import ProjectStage, WorkflowStepTemplate, WorkflowTemplate
        tpl = WorkflowTemplate.objects.create(name="قالب گزارش")
        step = WorkflowStepTemplate.objects.create(template=tpl, order=1, title="مرحله")
        st = ProjectStage.objects.create(project=self.project, step_template=step, order=1, title="مرحله", status=ProjectStage.Status.IN_PROGRESS)

        self.client.force_login(self.accountant_user)
        
        response = self.client.get(reverse("finance:accounting_reports"), {
            "start_date": "1405/05/01",
            "end_date": "1405/05/30",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "finance/accounting_report.html")

        # چک کردن مبالغ در کانتکست
        report = response.context["report"]
        self.assertEqual(report["total_revenue"], Decimal("500000"))
        self.assertEqual(report["operational_costs_sum"], Decimal("50000"))
        self.assertEqual(report["total_expenses"], Decimal("50000"))
        self.assertEqual(report["net_difference"], Decimal("450000"))

        admin_user = User.objects.create_user(username="rep_adm", role=User.Role.ADMIN)
        suspend_stage(st, actor=admin_user, comment="تعلیق")

        response_held = self.client.get(reverse("finance:accounting_reports"), {
            "start_date": "1405/05/01",
            "end_date": "1405/05/30",
        })
        report_held = response_held.context["report"]
        self.assertEqual(report_held["total_revenue"], Decimal("0"))
        self.assertEqual(report_held["operational_costs_sum"], Decimal("0"))

    def test_export_financial_report_to_csv(self):
        self.client.force_login(self.accountant_user)
        
        response = self.client.get(reverse("finance:accounting_reports"), {
            "start_date": "1405/05/01",
            "end_date": "1405/05/30",
            "export": "csv",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
