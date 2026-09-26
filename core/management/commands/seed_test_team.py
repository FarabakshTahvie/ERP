from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.models import Specialty, Party


class Command(BaseCommand):
    help = (
        "ساخت کاربران تیم برای تست دستی از صفر: یک مدیر، دو تکنسین برای هر تخصص، "
        "یک شریک تجاری نمونه و یک کارفرمای نمونه. هیچ پروژه/فاکتوری نمی‌سازد و "
        "روی WorkflowTemplate دست نمی‌زند."
    )

    TEST_PASSWORD = "Test@1234"

    def handle(self, *args, **options):
        credentials = []

        with transaction.atomic():
            sp_duct, _ = Specialty.objects.get_or_create(name="کانال‌کش")
            sp_design, _ = Specialty.objects.get_or_create(name="طراح اتوکد")
            sp_cnc, _ = Specialty.objects.get_or_create(name="اپراتور CNC")
            sp_assembler, _ = Specialty.objects.get_or_create(name="مونتاژکار")
            sp_reception, _ = Specialty.objects.get_or_create(name="پذیرش")
            sp_installer, _ = Specialty.objects.get_or_create(name="نصاب")
            sp_driver, _ = Specialty.objects.get_or_create(name="راننده")
            sp_warehouse, _ = Specialty.objects.get_or_create(name="انباردار")

            def upsert_user(username, first, last, role, phone, specialties=None,
                             is_superuser=False, party=None):
                user, _ = User.objects.update_or_create(
                    username=username,
                    defaults=dict(
                        first_name=first, last_name=last, role=role,
                        phone_number=phone, party=party,
                    ),
                )
                user.set_password(self.TEST_PASSWORD)
                if role in [User.Role.ADMIN, User.Role.EMPLOYEE]:
                    user.is_staff = True
                if is_superuser:
                    user.is_superuser = True
                user.must_change_password = False
                user.save()
                if specialties is not None:
                    user.specialties.set(specialties)
                credentials.append((role, username, phone, self.TEST_PASSWORD))
                return user

            # مدیر
            upsert_user("manager_test", "سارا", "مدیری", User.Role.ADMIN,
                        "09300000001", is_superuser=True)

            # دو تکنسین برای هر تخصص (برای تست Claim و انتقال کار بین هم‌تخصص‌ها)
            upsert_user("tech_kanal_1", "رضا", "کانالکش‌یک", User.Role.EMPLOYEE,
                        "09300000011", specialties=[sp_duct])
            upsert_user("tech_kanal_2", "علی", "کانالکش‌دو", User.Role.EMPLOYEE,
                        "09300000012", specialties=[sp_duct])
            upsert_user("tech_tarah_1", "مریم", "طراح‌یک", User.Role.EMPLOYEE,
                        "09300000021", specialties=[sp_design])
            upsert_user("tech_tarah_2", "زهرا", "طراح‌دو", User.Role.EMPLOYEE,
                        "09300000022", specialties=[sp_design])
            upsert_user("tech_cnc_1", "حسن", "سی‌ان‌سی‌یک", User.Role.EMPLOYEE,
                        "09300000031", specialties=[sp_cnc])
            upsert_user("tech_cnc_2", "محمد", "سی‌ان‌سی‌دو", User.Role.EMPLOYEE,
                        "09300000032", specialties=[sp_cnc])
            upsert_user("tech_montaj_1", "امیر", "مونتاژ‌یک", User.Role.EMPLOYEE,
                        "09300000041", specialties=[sp_assembler])
            upsert_user("tech_montaj_2", "کاوه", "مونتاژ‌دو", User.Role.EMPLOYEE,
                        "09300000042", specialties=[sp_assembler])
            upsert_user("tech_reception_1", "کهندل", "پذیرش", User.Role.EMPLOYEE,
                        "09300000071", specialties=[sp_reception])
            upsert_user("tech_nasab_1", "ساقی", "نصاب", User.Role.EMPLOYEE,
                        "09300000081", specialties=[sp_installer])
            upsert_user("tech_driver_1", "کیوان", "راننده", User.Role.EMPLOYEE,
                        "09300000091", specialties=[sp_driver])
            upsert_user("tech_warehouse_1", "نگار", "انباردار", User.Role.EMPLOYEE,
                        "09300000101", specialties=[sp_warehouse])

            # شریک تجاری نمونه
            partner_party, _ = Party.objects.update_or_create(
                phone_number="09300000051",
                defaults=dict(
                    entity_type=Party.EntityType.COMPANY, name="شرکت همکار تست",
                    company_registration_number="9999999", is_partner=True,
                ),
            )
            upsert_user("partner_test", "امیر", "همکار", User.Role.PARTNER,
                        "09300000051", party=partner_party)

            # کارفرمای نمونه
            client_party, _ = Party.objects.update_or_create(
                phone_number="09300000061",
                defaults=dict(
                    entity_type=Party.EntityType.INDIVIDUAL, name="مشتری تست",
                    national_code="1111111111", is_client=True,
                ),
            )
            upsert_user("client_test", "حسین", "مشتری", User.Role.CLIENT,
                        "09300000061", party=client_party)

        self.stdout.write(self.style.SUCCESS("کاربران تیم با موفقیت ساخته/به‌روزرسانی شدند.\n"))
        self.stdout.write("=== اطلاعات ورود (رمز همه: Test@1234) ===")
        for role, username, phone, password in credentials:
            self.stdout.write(
                f"نقش: {role:10s} | یوزرنیم: {username:15s} | موبایل: {phone} | پسورد: {password}"
            )
