from django.core.management.base import BaseCommand
from projects.models import WorkflowStepTemplate

UPLOAD_STEP_TITLES = ["طراحی اولیه اتوکد", "تکمیل طراحی", "جی‌کدگیری"]


class Command(BaseCommand):
    help = "اصلاح allows_file_upload برای مراحلی که باید آپلود فایل داشته باشند ولی ندارند"

    def handle(self, *args, **options):
        qs = WorkflowStepTemplate.objects.filter(title__in=UPLOAD_STEP_TITLES, allows_file_upload=False)
        count = qs.count()
        qs.update(allows_file_upload=True)
        self.stdout.write(self.style.SUCCESS(f"{count} مرحله اصلاح شد."))
