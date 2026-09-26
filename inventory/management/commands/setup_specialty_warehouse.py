from django.core.management.base import BaseCommand
from core.models import Specialty


class Command(BaseCommand):
    help = "ساخت تخصص «انباردار» (در صورت نبود). این تخصص به هیچ WorkflowStepTemplate وصل نمی‌شود، چون جزو گردش‌کار پروژه نیست."

    def handle(self, *args, **options):
        specialty, created = Specialty.objects.get_or_create(name="انباردار")
        if created:
            self.stdout.write(self.style.SUCCESS(f"تخصص «انباردار» ساخته شد (#{specialty.id})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"تخصص «انباردار» از قبل وجود داشت (#{specialty.id})."))
