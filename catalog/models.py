from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


class ItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="نام دسته")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children', verbose_name="دسته والد")

    class Meta:
        verbose_name = "دسته‌بندی کالا"
        verbose_name_plural = "دسته‌بندی‌های کالا"

    def __str__(self):
        return self.name


class Item(TimeStampedModel):
    """
    ثبت متریال و قطعات در یک جدول واحد نگه داشته می‌شود چون منطق انبار
    (لات، FIFO، میانگین موزون، هشدار موجودی) برای هر دو یکسان است.
    """

    class ItemType(models.TextChoices):
        MATERIAL = "material", "متریال"
        PART = "part", "قطعه"
        CONSUMABLE = "consumable", "مصرفی"

    class Unit(models.TextChoices):
        METER = "meter", "متر"
        SQUARE_METER = "sqm", "متر مربع"
        CUBIC_METER = "cbm", "متر مکعب"
        LITER = "liter", "لیتر"
        KILOGRAM = "kg", "کیلوگرم"
        PIECE = "piece", "عدد"

    name = models.CharField(max_length=255, verbose_name="نام کالا")
    item_type = models.CharField(max_length=20, choices=ItemType.choices, verbose_name="نوع کالا")
    category = models.ForeignKey(ItemCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="items", verbose_name="دسته‌بندی")
    unit = models.CharField(max_length=20, choices=Unit.choices, verbose_name="واحد سنجش")
    reorder_point = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="حداقل موجودی برای هشدار")
    specs = models.JSONField(
        default=dict, blank=True,
        verbose_name="مشخصات فنی",
        help_text='به‌صورت جفت برچسب-مقدار، مثلاً: {"جنس": "گالوانیزه", "ضخامت ورق": "0.6 تا 1.2 میلیمتر", "قطر": "100 تا 1600 میلیمتر", "نوع اتصال": "کوپلر یا فلنج"}',
    )
    responsible_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="responsible_items", verbose_name="مسئول هشدار موجودی")
    moving_average_cost = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="میانگین موزون قیمت (خودکار)")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "کالا (متریال/قطعه)"
        verbose_name_plural = "کالاها (متریال/قطعات)"

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"

    @property
    def current_stock(self):
        from inventory.models import StockLot
        return StockLot.objects.filter(item=self).aggregate(total=models.Sum('qty_remaining'))['total'] or 0


class Service(TimeStampedModel):
    """درختی: parent=None یعنی دسته‌ی سطح بالا؛ فقط برگ‌ها (بدون children) روی پروژه انتخاب می‌شوند."""
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children', verbose_name="والد")
    name = models.CharField(max_length=255, verbose_name="نام خدمت")
    code = models.CharField(max_length=30, blank=True, null=True, unique=True, verbose_name="کد خدمت")
    unit = models.CharField(max_length=20, choices=Item.Unit.choices, blank=True, verbose_name="واحد سنجش")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        verbose_name = "خدمت"
        verbose_name_plural = "خدمات"

    def __str__(self):
        return self.name

    @property
    def is_leaf(self):
        return not self.children.exists()


class ServiceBOM(models.Model):
    """فهرست متریال مورد نیاز هر خدمت — اختیاری، فقط برای برآورد اولیه، نه محاسبه‌ی خودکار قیمت فاکتور."""
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="bom_lines", verbose_name="خدمت")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="used_in_services", verbose_name="کالا")
    qty_per_unit = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار به ازای هر واحد خدمت")
    waste_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="درصد ضایعات")
    is_optional = models.BooleanField(default=False, verbose_name="اختیاری")

    class Meta:
        verbose_name = "متریال مورد نیاز خدمت"
        verbose_name_plural = "متریال‌های مورد نیاز خدمات"
        unique_together = ("service", "item")


class MarginRule(models.Model):
    """سود روی متریال/قطعه که در طول زمان تغییر می‌کند، بدون اینکه فاکتورهای قدیمی عوض شوند."""

    class ValueType(models.TextChoices):
        PERCENT = "percent", "درصد"
        FIXED = "fixed", "مبلغ ثابت (تومان)"

    class Scope(models.TextChoices):
        ITEM = "item", "کالای مشخص"
        CATEGORY = "category", "دسته‌بندی"
        GLOBAL = "global", "سراسری"

    scope = models.CharField(max_length=20, choices=Scope.choices, verbose_name="محدوده اعمال")
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.CASCADE, related_name="margin_rules", verbose_name="کالا")
    category = models.ForeignKey(ItemCategory, null=True, blank=True, on_delete=models.CASCADE, related_name="margin_rules", verbose_name="دسته‌بندی")
    value_type = models.CharField(max_length=20, choices=ValueType.choices, verbose_name="نوع مقدار")
    value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="مقدار")
    valid_from = models.DateTimeField(verbose_name="اعتبار از تاریخ")
    valid_to = models.DateTimeField(null=True, blank=True, verbose_name="اعتبار تا تاریخ (خالی=بدون انقضا)")
    priority = models.PositiveSmallIntegerField(default=0, verbose_name="اولویت")

    class Meta:
        verbose_name = "قانون سود"
        verbose_name_plural = "قوانین سود"
        ordering = ["-priority", "-valid_from"]
