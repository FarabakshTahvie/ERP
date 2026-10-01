from django.core.management.base import BaseCommand
from projects.workflow_v2 import build_workflow_v2


class Command(BaseCommand):
    help = "ساخت (idempotent) گردش‌کار نسخه‌ی ۲؛ با --make-default پیش‌فرض پروژه‌های تازه می‌شود."

    def add_arguments(self, parser):
        parser.add_argument("--make-default", action="store_true")

    def handle(self, *args, **options):
        template, created = build_workflow_v2(make_default=options["make_default"])
        self.stdout.write(self.style.SUCCESS(
            f"{'ساخته شد' if created else 'از قبل بود'}: {template.name} ({template.steps.count()} مرحله)"
            f"{' — پیش‌فرض شد' if options['make_default'] else ''}"
        ))
