from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from core.models import TimeStampedModel


class Warehouse(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام انبار")
    is_default = models.BooleanField(default=False, verbose_name="انبار پیش‌فرض")

    class Meta:
        verbose_name = "انبار"
        verbose_name_plural = "انبارها"

    def __str__(self):
        return self.name


class Purchase(TimeStampedModel):
    supplier = models.ForeignKey('core.Party', on_delete=models.PROTECT, related_name="purchases", verbose_name="فروشنده/تأمین‌کننده")
    invoice_number = models.CharField(max_length=50, blank=True, verbose_name="شماره فاکتور خرید")
    invoice_file = models.FileField(upload_to="purchases/invoices/", null=True, blank=True, verbose_name="فایل فاکتور خرید")
    purchased_at = models.DateTimeField(verbose_name="تاریخ خرید")
    notes = models.TextField(blank=True, verbose_name="یادداشت")

    class Meta:
        verbose_name = "سند خرید"
        verbose_name_plural = "اسناد خرید"

    def __str__(self):
        from utils.jalali import jalali_str
        return f"خرید از {self.supplier} - {jalali_str(self.purchased_at, fmt='%Y/%m/%d')}"


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(Purchase, on_delete=models.CASCADE, related_name="lines", verbose_name="سند خرید")
    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="purchase_lines", verbose_name="کالا")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="purchase_lines", verbose_name="انبار مقصد")
    qty = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار")
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="بهای خرید واحد (تومان)")

    class Meta:
        verbose_name = "ردیف خرید"
        verbose_name_plural = "ردیف‌های خرید"


class StockLot(TimeStampedModel):
    """هر خرید یک لات جدید می‌سازد؛ پایه‌ی FIFO و بهای واقعی."""
    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="lots", verbose_name="کالا")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="lots", verbose_name="انبار")
    purchase_line = models.ForeignKey(PurchaseLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="lots", verbose_name="ردیف خرید مبدأ")
    qty_in = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار ورودی اولیه")
    qty_remaining = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار باقی‌مانده")
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="بهای تمام‌شده واحد (تومان)")
    received_at = models.DateTimeField(verbose_name="تاریخ ورود به انبار")

    class Meta:
        verbose_name = "لات موجودی"
        verbose_name_plural = "لات‌های موجودی"
        ordering = ["received_at"]  # قدیمی‌ترین اول -> پایه‌ی FIFO


class StockMovement(TimeStampedModel):
    """رکورد append-only. هیچ رکوردی ویرایش/حذف نمی‌شود؛ اصلاح = حرکت معکوس جدید."""

    class MovementType(models.TextChoices):
        IN = "in", "ورود"
        OUT = "out", "خروج (مصرف)"
        RETURN = "return", "برگشت به انبار"
        ADJUST = "adjust", "اصلاح دستی"
        TRANSFER = "transfer", "انتقال بین انبارها"

    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="movements", verbose_name="کالا")
    lot = models.ForeignKey(StockLot, on_delete=models.PROTECT, related_name="movements", verbose_name="لات")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices, verbose_name="نوع حرکت")
    qty = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار")
    unit_cost = models.DecimalField(max_digits=18, decimal_places=2, verbose_name="بهای واحد در لحظه حرکت (تومان)")

    related_content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("related_content_type", "related_object_id")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements", verbose_name="ثبت‌کننده")
    notes = models.CharField(max_length=255, blank=True, verbose_name="یادداشت")

    class Meta:
        verbose_name = "حرکت انبار"
        verbose_name_plural = "حرکت‌های انبار"
        indexes = [models.Index(fields=["item", "-created_at"])]
