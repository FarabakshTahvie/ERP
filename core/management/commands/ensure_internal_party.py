from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Party


class Command(BaseCommand):
    help = "اطمینان از وجود طرف‌حساب داخلی شرکت (is_internal=True)؛ اگر نبود می‌سازد."

    def handle(self, *args, **options):
        existing = Party.objects.filter(is_internal=True).first()
        if existing:
            self.stdout.write(self.style.SUCCESS(f"طرف‌حساب داخلی از قبل وجود دارد: {existing.name} (#{existing.id})"))
            return

        contact = getattr(settings, "COMPANY_CONTACT", {})
        phone = contact.get("office_phone", {}).get("tel", "")
        party = Party.objects.create(
            entity_type=Party.EntityType.COMPANY,
            name="فرابخش تهویه (حساب داخلی شرکت)",
            phone_number=phone,
            company_registration_number="INTERNAL-1",
            is_internal=True,
            is_partner=True,
        )
        self.stdout.write(self.style.SUCCESS(f"طرف‌حساب داخلی ساخته شد: {party.name} (#{party.id})"))
