from django.core.management.base import BaseCommand
from core.models import Specialty
from projects.models import WorkflowStepTemplate


class Command(BaseCommand):
    help = "ساخت تخصص‌های «نصاب» و «راننده» و اتصال آن‌ها به مراحل نصب و ارسال در همه‌ی قالب‌های گردش‌کار"

    def handle(self, *args, **options):
        sp_installer, created_installer = Specialty.objects.get_or_create(name="نصاب")
        sp_driver, created_driver = Specialty.objects.get_or_create(name="راننده")

        updated_install = WorkflowStepTemplate.objects.filter(title="نصب").update(responsible_specialty=sp_installer)
        updated_shipping = WorkflowStepTemplate.objects.filter(title="ارسال").update(responsible_specialty=sp_driver)

        self.stdout.write(self.style.SUCCESS(
            f"تخصص «نصاب» {'ساخته شد' if created_installer else 'از قبل بود'} — "
            f"{updated_install} مرحله‌ی «نصب» به آن وصل شد."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"تخصص «راننده» {'ساخته شد' if created_driver else 'از قبل بود'} — "
            f"{updated_shipping} مرحله‌ی «ارسال» به آن وصل شد."
        ))
