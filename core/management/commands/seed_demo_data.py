from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from core.models import Specialty, Party, PartyContact
from catalog.models import ItemCategory, Item, Service, ServiceBOM
from inventory.models import Warehouse, Purchase, PurchaseLine
from inventory.services import receive_stock
from projects.models import (
    Project, ProjectService, ProjectMaterial, ProjectParticipant,
    WorkflowTemplate, WorkflowStepTemplate,
)
from projects.services import create_project_stages_from_template, advance_stage
from finance.services import generate_invoice_for_project
from finance.models import Payment
from finance.services import approve_payment


class Command(BaseCommand):
    help = "ساخت داده‌های نمونه‌ی کامل برای تست جریان کار (کاربر، پروژه، انبار، فاکتور)"

    def handle(self, *args, **options):
        credentials = []

        with transaction.atomic():
            sp_duct, _ = Specialty.objects.get_or_create(name="کانال‌کش")
            sp_design, _ = Specialty.objects.get_or_create(name="طراح اتوکد")

            def make_user(username, first, last, role, phone, password="Test@1234", specialties=None):
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults=dict(first_name=first, last_name=last, role=role, phone_number=phone),
                )
                user.role = role
                user.phone_number = phone
                user.set_password(password)
                if role in [User.Role.ADMIN, User.Role.EMPLOYEE]:
                    user.is_staff = True
                user.save()
                if specialties:
                    user.specialties.set(specialties)
                credentials.append((role, username, password))
                return user

            admin_user = make_user("admin_demo", "سارا", "مدیری", User.Role.ADMIN, "09120000001")
            admin_user.is_superuser = True
            admin_user.save()

            tech_duct = make_user("tech_kanal", "رضا", "کانال‌کش", User.Role.EMPLOYEE, "09120000002", specialties=[sp_duct])
            tech_design = make_user("tech_tarah", "مریم", "طراح", User.Role.EMPLOYEE, "09120000003", specialties=[sp_design])

            partner_party = Party.objects.create(
                entity_type=Party.EntityType.COMPANY, name="شرکت همکار تهویه نوین",
                phone_number="02100000001", company_registration_number="12345", is_partner=True,
            )
            PartyContact.objects.create(party=partner_party, full_name="امیر رستمی", position="مدیر پروژه", phone_number="09120000004", is_primary=True)

            client_party = Party.objects.create(
                entity_type=Party.EntityType.INDIVIDUAL, name="حسین احمدی",
                phone_number="09120000005", national_code="0012345678", is_client=True,
            )

            partner_user = make_user("partner_demo", "امیر", "رستمی", User.Role.PARTNER, "09120000004")
            partner_user.party = partner_party
            partner_user.save()

            client_user = make_user("client_demo", "حسین", "احمدی", User.Role.CLIENT, "09120000005")
            client_user.party = client_party
            client_user.save()

            cat_sheet, _ = ItemCategory.objects.get_or_create(name="ورق و متریال کانال")
            item_sheet = Item.objects.create(
                name="ورق گالوانیزه ۱ میل", item_type=Item.ItemType.MATERIAL,
                category=cat_sheet, unit=Item.Unit.SQUARE_METER, reorder_point=10,
                specs={"جنس": "گالوانیزه", "ضخامت": "1 میلیمتر"},
            )

            service_duct = Service.objects.create(name="کانال‌کشی گالوانیزه", unit=Item.Unit.METER)
            ServiceBOM.objects.create(service=service_duct, item=item_sheet, qty_per_unit=2, waste_percent=5)

            warehouse, _ = Warehouse.objects.get_or_create(name="انبار مرکزی", defaults={"is_default": True})

            p1 = Purchase.objects.create(supplier=partner_party, purchased_at=timezone.now() - timedelta(days=10), invoice_number="PB-001")
            l1 = PurchaseLine.objects.create(purchase=p1, item=item_sheet, warehouse=warehouse, qty=5, unit_cost=1500000)
            receive_stock(item=item_sheet, warehouse=warehouse, qty=5, unit_cost=1500000, received_at=p1.purchased_at, purchase_line=l1)

            p2 = Purchase.objects.create(supplier=partner_party, purchased_at=timezone.now() - timedelta(days=3), invoice_number="PB-002")
            l2 = PurchaseLine.objects.create(purchase=p2, item=item_sheet, warehouse=warehouse, qty=5, unit_cost=1700000)
            receive_stock(item=item_sheet, warehouse=warehouse, qty=5, unit_cost=1700000, received_at=p2.purchased_at, purchase_line=l2)

            sp_cnc, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
            sp_assembler, _ = Specialty.objects.get_or_create(name="مونتاژکار")

            template = WorkflowTemplate.objects.create(name="گردش‌کار پیش‌فرض تهویه", is_default=True)
            steps_data = [
                # title, client_label, specialty, approval_by, allows_file_upload
                ("صدور پیش‌فاکتور", "صدور پیش‌فاکتور", None, "admin", False),
                ("تایید پیش‌فاکتور و انتخاب روش پرداخت", "تایید پیش‌فاکتور", None, "choose_at_runtime", False),
                ("بازدید کارگاهی", "بازدید و اندازه‌گیری", sp_duct, "none", False),
                ("طراحی اولیه اتوکد", "طراحی اولیه", sp_design, "none", True),
                ("تایید طرح اولیه", "تایید نقشه اولیه", None, "choose_at_runtime", False),
                ("تکمیل طراحی", "طراحی نهایی", sp_design, "none", True),
                ("جی‌کدگیری", "آماده‌سازی برش (جی‌کدگیری)", sp_cnc, "none", False),
                ("برش‌کاری", "برش", sp_duct, "none", False),
                ("مونتاژ", "مونتاژ", sp_assembler, "none", False),
                ("ارسال", "ارسال به محل نصب", None, "none", False),
                ("نصب", "نصب نهایی", sp_duct, "admin", False),
            ]
            step_objs = []
            for i, (title, client_label, specialty, approval, upload) in enumerate(steps_data, start=1):
                step_objs.append(WorkflowStepTemplate.objects.create(
                    template=template, order=i, title=title, client_label=client_label,
                    responsible_specialty=specialty, approval_by=approval,
                    allows_file_upload=upload, client_visible=True,
                    estimated_duration_hours=8 if specialty else 4,
                ))
            step_objs[4].on_reject_go_to = step_objs[3]   # رد «تایید طرح اولیه» → برگشت به «طراحی اولیه اتوکد»
            step_objs[4].save()

            project = Project.objects.create(
                name="پروژه نمونه - ساختمان اداری الف", partner=partner_party, owner=client_party,
                workflow_template=template, contract_date=timezone.localdate(),
                installation_fee=15000000, shipping_fee=2000000, extra_fee=0,
                created_by=admin_user,
            )
            project.assigned_technicians.add(tech_duct, tech_design)
            ProjectService.objects.create(project=project, service=service_duct, qty=40, unit_price=850000)
            ProjectMaterial.objects.create(project=project, item=item_sheet, qty=10, unit_price=2200000)
            ProjectParticipant.objects.create(project=project, party=partner_party, role=ProjectParticipant.ParticipantRole.CONTRACTOR, agreed_cost=3000000)

            stages = create_project_stages_from_template(project)
            advance_stage(stages[0], actor=admin_user, new_status="done", comment="پیش‌فاکتور صادر و ارسال شد.")

            invoice = generate_invoice_for_project(project)
            payment1 = Payment.objects.create(invoice=invoice, method=Payment.Method.CARD_TO_CARD, amount=20000000, reference_number="TRX-0001")
            approve_payment(payment1, approved_by=admin_user, verified_amount=20000000)
            Payment.objects.create(
                invoice=invoice, method=Payment.Method.CREDIT,
                amount=invoice.total_amount - invoice.paid_amount,
                note="توافق شد باقی‌مانده تا پایان ماه به‌صورت اعتباری تسویه شود.",
            )

        self.stdout.write(self.style.SUCCESS("داده‌های نمونه ساخته شدند.\n"))
        self.stdout.write(self.style.SUCCESS(f"پروژه: {project.code} - {project.name}"))
        self.stdout.write(self.style.SUCCESS(f"فاکتور: {invoice.number}"))
        self.stdout.write(f"مانده فاکتور: {invoice.remaining_amount}")
        self.stdout.write(f"بدهکاری کل طرف‌حساب: {partner_party.total_outstanding}")
        self.stdout.write("\n=== اطلاعات ورود کاربران ===")
        for role, username, password in credentials:
            self.stdout.write(f"نقش: {role:10s} | یوزرنیم: {username:15s} | پسورد: {password}")
