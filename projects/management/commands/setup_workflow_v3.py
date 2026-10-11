from django.core.management.base import BaseCommand
from projects.workflow_v3 import build_workflow_v3, drop_unused_v2


class Command(BaseCommand):
    help = ("ساخت (idempotent) گردش‌کار نسخه‌ی ۳؛ با --make-default پیش‌فرض پروژه‌های تازه می‌شود. "
            "قالب v2 قدیمی را فقط وقتی هیچ پروژه‌ای به آن وصل نیست پاک می‌کند.")

    def add_arguments(self, parser):
        parser.add_argument("--make-default", action="store_true")

    def handle(self, *args, **options):
        template, created = build_workflow_v3(make_default=options["make_default"])
        dropped = drop_unused_v2()
        self.stdout.write(self.style.SUCCESS(
            f"{'ساخته شد' if created else 'از قبل بود'}: {template.name} ({template.steps.count()} مرحله)"
            f"{' — پیش‌فرض شد' if options['make_default'] else ''}"
            f"{' — قالب v2 قدیمی پاک شد' if dropped else ''}"
        ))
