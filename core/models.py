from django.db import models
from simple_history.models import HistoricalRecords


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاریخ ایجاد")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاریخ بروزرسانی")

    class Meta:
        abstract = True


class Specialty(models.Model):
    """
    تخصص فنی تکنسین‌ها (برقکار، لوله‌کش، نصاب کانال و ...).
    عمداً یک جدول جداست نه choices روی User.role، چون این فهرست باز است و
    باید بدون تغییر کد/دیپلوی، از پنل ادمین قابل افزودن باشد.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="نام تخصص")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "تخصص"
        verbose_name_plural = "تخصص‌ها"

    def __str__(self):
        return self.name


class Location(TimeStampedModel):
    title = models.CharField(max_length=255, blank=True, verbose_name="عنوان مکان")
    address_text = models.TextField(blank=True, verbose_name="آدرس به‌صورت متنی (دستی)")
    city = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="شهر")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="عرض جغرافیایی")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="طول جغرافیایی")

    class Meta:
        verbose_name = "موقعیت مکانی"
        verbose_name_plural = "موقعیت‌های مکانی"

    def __str__(self):
        return self.title or (self.address_text[:40] if self.address_text else f"لوکیشن #{self.pk}")

    @property
    def has_exact_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class Party(TimeStampedModel):
    """
    طرف‌حساب عمومی. نقش‌ها (شریک تجاری/کارفرما/پیمانکار/تأمین‌کننده) به‌صورت فلگ‌های مستقل‌اند
    چون یک شرکت می‌تواند هم‌زمان چند نقش داشته باشد. entity_type فقط می‌گوید شخص است یا شرکت.
    """

    class EntityType(models.TextChoices):
        INDIVIDUAL = "individual", "شخص حقیقی"
        COMPANY = "company", "شخص حقوقی (شرکت)"

    entity_type = models.CharField(max_length=20, choices=EntityType.choices, default=EntityType.INDIVIDUAL, verbose_name="نوع شخص")
    name = models.CharField(max_length=255, verbose_name="نام / نام شرکت")
    brand_name = models.CharField(max_length=255, blank=True, verbose_name="نام برند/تجاری")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="شماره تماس")
    secondary_phone = models.CharField(max_length=20, blank=True, verbose_name="شماره تماس دوم")
    email = models.EmailField(blank=True, verbose_name="ایمیل")
    national_code = models.CharField(max_length=10, blank=True, null=True, unique=True, verbose_name="کد ملی")
    company_registration_number = models.CharField(max_length=30, blank=True, null=True, unique=True, verbose_name="شماره ثبت شرکت")
    company_economic_code = models.CharField(max_length=30, blank=True, null=True, unique=True, verbose_name="شناسه/کد اقتصادی")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True, related_name="parties", verbose_name="موقعیت مکانی")
    description = models.TextField(blank=True, verbose_name="توضیحات")

    is_partner = models.BooleanField(default=False, verbose_name="شریک تجاری")
    is_client = models.BooleanField(default=False, verbose_name="کارفرما")
    is_contractor = models.BooleanField(default=False, verbose_name="پیمانکار")
    is_supplier = models.BooleanField(default=False, verbose_name="تأمین‌کننده")
    is_internal = models.BooleanField(default=False, verbose_name="حساب داخلی شرکت خودمان")

    credit_limit = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="سقف اعتبار (تومان)")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "طرف‌حساب"
        verbose_name_plural = "طرف‌حساب‌ها"
        constraints = [
            models.UniqueConstraint(
                fields=["is_internal"], condition=models.Q(is_internal=True),
                name="unique_internal_party",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_entity_type_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.entity_type == self.EntityType.INDIVIDUAL and not self.national_code:
            raise ValidationError("برای شخص حقیقی، کد ملی الزامی است.")
        if self.entity_type == self.EntityType.COMPANY and not (self.company_registration_number or self.company_economic_code):
            raise ValidationError("برای شرکت، حداقل یکی از شماره ثبت یا شناسه اقتصادی باید ثبت شود.")
        if not (self.is_partner or self.is_client or self.is_contractor or self.is_supplier or self.is_internal):
            raise ValidationError("حداقل یکی از نقش‌های طرف‌حساب باید انتخاب شود.")

    @property
    def balance(self):
        """مانده حساب: مثبت یعنی طرف‌حساب به ما بدهکار است."""
        from django.db.models import Sum
        from finance.models import LedgerEntry
        debit = self.ledger_entries.filter(entry_type=LedgerEntry.EntryType.DEBIT).aggregate(s=Sum('amount'))['s'] or 0
        credit = self.ledger_entries.filter(entry_type=LedgerEntry.EntryType.CREDIT).aggregate(s=Sum('amount'))['s'] or 0
        return debit - credit

    @property
    def total_outstanding(self):
        """مجموع مبلغ باقی‌مانده‌ی همه‌ی فاکتورهای این طرف‌حساب که لغو نشده‌اند."""
        from finance.models import Invoice
        invoices = self.invoices.exclude(status=Invoice.Status.CANCELLED)
        total = sum((inv.remaining_amount for inv in invoices), 0)
        return total


class PartyContact(TimeStampedModel):
    party = models.ForeignKey(Party, on_delete=models.CASCADE, related_name="contacts", verbose_name="طرف‌حساب")
    full_name = models.CharField(max_length=255, verbose_name="نام و نام خانوادگی")
    position = models.CharField(max_length=100, blank=True, verbose_name="سمت")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="شماره تماس")
    is_primary = models.BooleanField(default=False, verbose_name="رابط اصلی")

    class Meta:
        verbose_name = "رابط طرف‌حساب"
        verbose_name_plural = "رابط‌های طرف‌حساب"

    def __str__(self):
        return f"{self.full_name} ({self.party.name})"
