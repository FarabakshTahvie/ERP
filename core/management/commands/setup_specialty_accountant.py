from django.core.management.base import BaseCommand
from core.models import Specialty


class Command(BaseCommand):
    help = "ساخت تخصص «حسابدار» (در صورت نبود). حسابدار هم دسترسی انباردار و هم دسترسی پذیرش را دارد (projects.services.user_is_accountant)."

    def handle(self, *args, **options):
        specialty, created = Specialty.objects.get_or_create(name="حسابدار")
        if created:
            self.stdout.write(self.style.SUCCESS(f"تخصص «حسابدار» ساخته شد (#{specialty.id})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"تخصص «حسابدار» از قبل وجود داشت (#{specialty.id})."))
