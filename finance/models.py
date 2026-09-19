import uuid
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel


class Invoice(TimeStampedModel):
    class DocumentType(models.TextChoices):
        PROFORMA = "proforma", "پیش‌فاکتور"
        FINAL = "final", "فاکتور قطعی"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        SENT = "sent", "ارسال‌شده"
        AWAITING_APPROVAL = "awaiting_approval", "در انتظار تایید"
        PARTIALLY_PAID = "partially_paid", "پرداخت ناقص"
        PAID = "paid", "تسویه‌شده"
        CANCELLED = "cancelled", "لغوشده"

    project = models.OneToOneField('projects.Project', on_delete=models.PROTECT, related_name="invoice", verbose_name="پروژه")
    number = models.CharField(max_length=30, unique=True, verbose_name="شماره فاکتور")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices, default=DocumentType.PROFORMA, verbose_name="نوع سند")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name="وضعیت")

    billed_party = models.ForeignKey('core.Party', on_delete=models.PROTECT, related_name="invoices", verbose_name="طرف‌حساب فاکتور")
    address_snapshot = models.TextField(blank=True, verbose_name="آدرس (کپی‌شده در لحظه صدور)")

    total_amount = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="مبلغ کل (تومان)")
    paid_amount = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="مبلغ پرداخت‌شده (محاسبه خودکار)")

    contract_date = models.DateField(null=True, blank=True, verbose_name="تاریخ عقد قرارداد")
    issue_date = models.DateField(verbose_name="تاریخ صدور")
    due_date = models.DateField(null=True, blank=True, verbose_name="تاریخ سررسید")
    settled_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تسویه کامل")

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="شناسه یکتا")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "فاکتور"
        verbose_name_plural = "فاکتورها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} - {self.project.name}"

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount


class InvoiceLine(models.Model):
    class LineType(models.TextChoices):
        SERVICE = "service", "خدمت"
        MATERIAL = "material", "متریال"
        INSTALLATION = "installation", "هزینه نصب"
        SHIPPING = "shipping", "هزینه ارسال"
        EXTRA = "extra", "هزینه مازاد"
        DISCOUNT = "discount", "تخفیف"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines", verbose_name="فاکتور")
    line_type = models.CharField(max_length=20, choices=LineType.choices, verbose_name="نوع ردیف")
    title = models.CharField(max_length=255, verbose_name="عنوان (اسنپ‌شات)")
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="مقدار")
    unit_price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="قیمت واحد (تومان، برای تخفیف منفی وارد شود)")
    cost_snapshot = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True, verbose_name="بهای تمام‌شده (اسنپ‌شات برای گزارش سود)")
    total = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="جمع ردیف (تومان)")

    class Meta:
        verbose_name = "ردیف فاکتور"
        verbose_name_plural = "ردیف‌های فاکتور"

    def save(self, *args, **kwargs):
        self.total = self.qty * self.unit_price
        super().save(*args, **kwargs)


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        GATEWAY = "gateway", "درگاه پرداخت"
        CARD_TO_CARD = "card_to_card", "کارت به کارت"
        RECEIPT = "receipt", "رسید واریز"
        CHEQUE = "cheque", "چک"
        CREDIT = "credit", "اعتباری"

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار تایید"
        APPROVED = "approved", "تاییدشده"
        REJECTED = "rejected", "رد شده"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments", verbose_name="فاکتور")
    method = models.CharField(max_length=20, choices=Method.choices, verbose_name="روش پرداخت")
    amount = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ (تومان)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="وضعیت")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پرداخت")
    reference_number = models.CharField(max_length=100, blank=True, verbose_name="شماره پیگیری/تراکنش")
    receipt_file = models.FileField(upload_to="payments/receipts/", null=True, blank=True, verbose_name="تصویر رسید/فیش")
    note = models.TextField(blank=True, verbose_name="توضیحات (به‌خصوص برای روش اعتباری)")

    cheque_number = models.CharField(max_length=30, blank=True, verbose_name="شماره صیادی چک")
    cheque_bank = models.CharField(max_length=100, blank=True, verbose_name="بانک")
    cheque_due_date = models.DateField(null=True, blank=True, verbose_name="تاریخ سررسید چک")

    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_payments", verbose_name="تاییدکننده")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تایید")

    class Meta:
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.method == self.Method.GATEWAY and self.status == self.Status.PENDING:
            self.status = self.Status.APPROVED
            self.approved_at = self.approved_at or timezone.now()
        super().save(*args, **kwargs)
        from .services import recalculate_invoice_paid_amount
        recalculate_invoice_paid_amount(self.invoice)


class LedgerEntry(TimeStampedModel):
    class EntryType(models.TextChoices):
        DEBIT = "debit", "بدهکار (طرف‌حساب به ما بدهکار است)"
        CREDIT = "credit", "بستانکار (طرف‌حساب طلبکار است)"

    party = models.ForeignKey('core.Party', on_delete=models.PROTECT, related_name="ledger_entries", verbose_name="طرف‌حساب")
    entry_type = models.CharField(max_length=20, choices=EntryType.choices, verbose_name="نوع")
    amount = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ (تومان)")
    description = models.CharField(max_length=255, blank=True, verbose_name="شرح")

    related_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    class Meta:
        verbose_name = "سند دفتر حساب"
        verbose_name_plural = "اسناد دفتر حساب"
        ordering = ["-created_at"]
