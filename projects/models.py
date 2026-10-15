import os
from django.conf import settings
from django.db import models, transaction, IntegrityError
from django.utils import timezone
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel


class StageKind(models.TextChoices):
    GENERIC = "generic", "عمومی"
    VISIT = "visit", "بازدید"
    PROFORMA = "proforma", "صدور پیش‌فاکتور"
    DESIGN_INITIAL = "design_initial", "طراحی اولیه"
    GCODE = "gcode", "جی‌کدگیری"
    CUTTING = "cutting", "برش‌کاری"
    SHIPPING = "shipping", "ارسال"
    ASSEMBLY = "assembly", "مونتاژ"
    INSTALL = "install", "نصب"
    FINAL_REVIEW = "final_review", "بازبینی نهایی"



class Project(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        IN_PROGRESS = "in_progress", "در حال اجرا"
        COMPLETED = "completed", "تکمیل‌شده"
        CANCELLED = "cancelled", "لغو‌شده"

    code = models.CharField(max_length=30, unique=True, blank=True, verbose_name="کد پروژه")
    name = models.CharField(max_length=255, verbose_name="نام پروژه")

    partner = models.ForeignKey('core.Party', on_delete=models.PROTECT, related_name="projects_as_partner", limit_choices_to={"is_partner": True}, verbose_name="شریک تجاری")
    owner = models.ForeignKey('core.Party', on_delete=models.SET_NULL, null=True, blank=True, related_name="projects_as_owner", limit_choices_to={"is_client": True}, verbose_name="صاحب ملک / کارفرمای اصلی")
    location = models.ForeignKey('core.Location', on_delete=models.SET_NULL, null=True, blank=True, related_name="projects", verbose_name="موقعیت مکانی پروژه")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name="وضعیت")
    workflow_template = models.ForeignKey('WorkflowTemplate', null=True, blank=True, on_delete=models.SET_NULL, related_name="projects", verbose_name="قالب گردش‌کار")

    visit_date = models.DateField(null=True, blank=True, verbose_name="تاریخ بازدید")
    contract_date = models.DateField(null=True, blank=True, verbose_name="تاریخ عقد قرارداد")
    actual_end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ دقیق اتمام")

    installation_fee = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="هزینه نصب (تومان)")
    shipping_fee = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="هزینه ارسال (تومان)")
    extra_fee = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="هزینه‌های مازاد دستی (تومان)")

    notes = models.TextField(blank=True, verbose_name="یادداشت")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects", verbose_name="ثبت‌کننده")
    assigned_technicians = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assigned_projects", verbose_name="تکنیسین‌های مسئول", limit_choices_to={"role": "employee"})
    history = HistoricalRecords()

    class Meta:
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه‌ها"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=['status', '-created_at'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.code:
            return super().save(*args, **kwargs)
        for attempt in range(5):   # دو ثبت هم‌زمان ممکن است یک کد بگیرند؛ کد unique است
            self.code = self._generate_code()
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if attempt == 4:
                    raise
                self.code = ""

    def _generate_code(self):
        from utils.utils import monthly_prefix, next_monthly_code
        return next_monthly_code(Project.objects.all(), "code", monthly_prefix("P"))


class ProjectService(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="services", verbose_name="پروژه")
    service = models.ForeignKey('catalog.Service', on_delete=models.PROTECT, related_name="project_lines", verbose_name="خدمت")
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="مقدار")
    unit_price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="قیمت واحد (تومان) - مخصوص همین پروژه")
    description = models.TextField(blank=True, verbose_name="توضیحات")

    class Meta:
        verbose_name = "خدمت پروژه"
        verbose_name_plural = "خدمات پروژه"

    @property
    def total(self):
        return self.qty * self.unit_price

    def __str__(self):
        return f"{self.service.name} × {self.qty}"


class ProjectServiceMaterial(models.Model):
    """کالای مصرفی زیر یک خدمت. فقط برای محاسبه‌ی قیمت خدمت؛ در فاکتور دیده نمی‌شود."""
    service_line = models.ForeignKey(ProjectService, on_delete=models.CASCADE, related_name="materials", verbose_name="خدمت پروژه")
    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="service_line_usages", verbose_name="کالا")
    qty = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار")
    cost_snapshot = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="میانگین موزون (اسنپ‌شات)")
    margin_percent = models.DecimalField(max_digits=7, decimal_places=2, default=0, verbose_name="سود ٪ (اسنپ‌شات)")
    line_total = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="جمع فروش (تومان)")

    class Meta:
        verbose_name = "کالای زیر خدمت"
        verbose_name_plural = "کالاهای زیر خدمت"


class ProjectExtraLine(models.Model):
    """ردیف دستی پیش‌فاکتور (هزینه‌ی اضافه یا تخفیف). مبلغ همیشه مثبت؛ علامت از kind."""

    class Kind(models.TextChoices):
        EXTRA = "extra", "هزینه‌ی اضافه"
        DISCOUNT = "discount", "تخفیف"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="extra_lines", verbose_name="پروژه")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.EXTRA, verbose_name="نوع")
    title = models.CharField(max_length=200, verbose_name="شرح (روی پیش‌فاکتور)")
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="مقدار")
    unit_price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ واحد (تومان)")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "ردیف دستی پیش‌فاکتور"
        verbose_name_plural = "ردیف‌های دستی پیش‌فاکتور"
        ordering = ["pk"]



class ProjectMaterial(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="extra_materials", verbose_name="پروژه")
    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="project_usages", verbose_name="کالا")
    qty = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار")
    unit_price = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="قیمت فروش واحد (تومان)")

    class Meta:
        verbose_name = "اضافه متریال پروژه"
        verbose_name_plural = "اضافه‌متریال‌های پروژه"

    @property
    def total(self):
        return self.qty * self.unit_price


class ProjectParticipant(models.Model):
    class ParticipantRole(models.TextChoices):
        CONTRACTOR = "contractor", "پیمانکار"
        ELECTRICIAN = "electrician", "برق‌کار"
        ASSEMBLER = "assembler", "مونتاژکار"
        SUPERVISOR = "supervisor", "ناظر"
        OTHER = "other", "سایر"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="participants", verbose_name="پروژه")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_participations", verbose_name="کاربر داخلی")
    party = models.ForeignKey('core.Party', on_delete=models.SET_NULL, null=True, blank=True, related_name="project_participations", verbose_name="طرف‌حساب بیرونی")
    role = models.CharField(max_length=20, choices=ParticipantRole.choices, verbose_name="نقش")
    # طبق تصمیم فعلی، این هزینه در فاکتور به‌صورت خودکار داخل «هزینه‌های مازاد» جمع می‌شود
    agreed_cost = models.DecimalField(max_digits=18, decimal_places=0, default=0, verbose_name="هزینه توافق‌شده (تومان)")
    notes = models.CharField(max_length=255, blank=True, verbose_name="یادداشت")

    class Meta:
        verbose_name = "عامل اجرایی پروژه"
        verbose_name_plural = "عوامل اجرایی پروژه"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.user and not self.party:
            raise ValidationError("باید یا کاربر داخلی یا طرف‌حساب بیرونی مشخص شود.")
        if self.user and self.party:
            raise ValidationError("فقط یکی از کاربر داخلی یا طرف‌حساب بیرونی باید پر شود.")

    def __str__(self):
        return f"{self.user or self.party} - {self.get_role_display()}"


# ----------------- گردش‌کار -----------------

class WorkflowTemplate(models.Model):
    name = models.CharField(max_length=100, verbose_name="نام قالب")
    is_default = models.BooleanField(default=False, verbose_name="قالب پیش‌فرض")

    class Meta:
        verbose_name = "قالب گردش‌کار"
        verbose_name_plural = "قالب‌های گردش‌کار"

    def __str__(self):
        return self.name


class WorkflowStepTemplate(models.Model):
    class ApprovalBy(models.TextChoices):
        NONE = "none", "بدون نیاز به تایید"
        ADMIN = "admin", "مدیر"
        PARTNER = "partner", "شریک تجاری"
        OWNER = "owner", "کارفرما/صاحب ملک"
        CHOOSE_AT_RUNTIME = "choose_at_runtime", "ادمین موقع ارسال انتخاب می‌کند"

    template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name="steps", verbose_name="قالب گردش‌کار")
    order = models.PositiveSmallIntegerField(verbose_name="ترتیب")
    title = models.CharField(max_length=150, verbose_name="عنوان داخلی مرحله")
    client_label = models.CharField(max_length=150, blank=True, verbose_name="عنوانی که کارفرما می‌بیند")
    kind = models.CharField(max_length=30, choices=StageKind.choices, default=StageKind.GENERIC, verbose_name="نوع رفتاری مرحله")
    assign_to_project_creator = models.BooleanField(default=False, verbose_name="مسئول = ثبت‌کننده‌ی پروژه")
    responsible_role = models.CharField(max_length=20, choices=[('manager', 'مدیر'), ('employee', 'تکنسین')], blank=True, verbose_name="نقش مسئول")
    responsible_specialty = models.ForeignKey('core.Specialty', null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_steps", verbose_name="تخصص مورد نیاز")
    approval_by = models.CharField(max_length=20, choices=ApprovalBy.choices, default=ApprovalBy.NONE, verbose_name="نیازمند تایید توسط")
    estimated_duration_hours = models.PositiveIntegerField(null=True, blank=True, verbose_name="مدت‌زمان تخمینی (ساعت)")
    client_visible = models.BooleanField(default=True, verbose_name="قابل نمایش به کارفرما")
    allows_file_upload = models.BooleanField(default=False, verbose_name="امکان آپلود فایل در این مرحله")
    requires_payment_selection = models.BooleanField(
        default=False, verbose_name="این مرحله نیازمند انتخاب روش پرداخت هم هست (نه فقط تایید ساده)"
    )
    default_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="default_assigned_steps", verbose_name="مسئول ثابت این مرحله (اختیاری)",
        help_text="اگر پر شود، این مرحله همیشه مستقیم به همین شخص ارجاع می‌شود بدون نیاز به Claim.",
    )
    on_reject_go_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name="rejected_from", verbose_name="در صورت رد، برگردد به این مرحله")

    class Meta:
        verbose_name = "مرحله قالب گردش‌کار"
        verbose_name_plural = "مراحل قالب گردش‌کار"
        ordering = ["template", "order"]
        unique_together = ("template", "order")

    def __str__(self):
        return f"{self.template.name} / {self.order}. {self.title}"


class ProjectStage(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        IN_PROGRESS = "in_progress", "در حال انجام"
        WAITING_APPROVAL = "waiting_approval", "در انتظار تایید"
        REJECTED = "rejected", "رد شده / نیازمند اصلاح"
        DONE = "done", "انجام‌شده"
        SUSPENDED = "suspended", "معلق - در انتظار بررسی مدیر"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stages", verbose_name="پروژه")
    step_template = models.ForeignKey(WorkflowStepTemplate, on_delete=models.PROTECT, related_name="stage_instances", verbose_name="مرحله قالب مرجع")
    order = models.PositiveSmallIntegerField(verbose_name="ترتیب")
    title = models.CharField(max_length=150, verbose_name="عنوان مرحله (کپی‌شده)")
    client_label = models.CharField(max_length=150, blank=True, verbose_name="عنوان نمایشی برای کارفرما")
    kind = models.CharField(max_length=30, choices=StageKind.choices, default=StageKind.GENERIC, verbose_name="نوع رفتاری")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="وضعیت")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_stages", verbose_name="مسئول انجام")
    candidate_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="candidate_stages",
        verbose_name="افراد واجد شرایط (تا زمانی که کسی کار را برندارد)",
    )
    client_visible = models.BooleanField(default=True, verbose_name="قابل نمایش به کارفرما")
    client_preview = models.BooleanField(default=False, verbose_name="فایل‌های این مرحله برای مشتری نمایش داده می‌شود")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان شروع")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان اتمام")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_stages", verbose_name="انجام‌دهنده")
    rejection_count = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد دفعات رد شدن")
    return_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="reopened_stages", verbose_name="بعد از تکمیل برگرد به")

    class Meta:
        verbose_name = "مرحله پروژه"
        verbose_name_plural = "مراحل پروژه"
        ordering = ["project", "order"]

    @property
    def needs_manual_assignment(self):
        return (
            self.status == self.Status.IN_PROGRESS
            and self.assigned_to_id is None
            and not self.candidate_users.exists()
        )

    def __str__(self):
        return f"{self.project.name} / {self.title}"


def stage_voice_path(instance, filename):
    return f"projects/{instance.stage.project_id}/voice/{filename}"


class StageEvent(models.Model):
    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="events", verbose_name="مرحله")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="stage_events", verbose_name="انجام‌دهنده")
    from_status = models.CharField(max_length=20, blank=True, verbose_name="وضعیت قبلی")
    to_status = models.CharField(max_length=20, verbose_name="وضعیت جدید")
    comment = models.TextField(blank=True, verbose_name="توضیح")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان")
    voice = models.FileField(upload_to=stage_voice_path, blank=True, verbose_name="پیام صوتی")
    voice_duration = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="مدت پیام صوتی (ثانیه)")
    voice_peaks = models.CharField(max_length=256, blank=True, verbose_name="شکل موج")

    class Meta:
        verbose_name = "رویداد مرحله"
        verbose_name_plural = "رویدادهای مرحله"
        ordering = ["created_at"]


class StageUsage(models.Model):
    """مصرف ثبت‌شده توسط تکنسین هر مرحله. هر مرحله مصرف خودش را دارد؛ از انبار کم نمی‌کند (کم‌شدن فقط در بازبینی نهایی)."""
    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="usages", verbose_name="مرحله")
    item = models.ForeignKey('catalog.Item', on_delete=models.PROTECT, related_name="stage_usages", verbose_name="کالا")
    qty = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="مقدار مصرف")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="ثبت‌کننده")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="آخرین ثبت")

    class Meta:
        verbose_name = "مصرف مرحله"
        verbose_name_plural = "مصرف مرحله‌ها"
        ordering = ["stage__order", "item__name"]
        constraints = [models.UniqueConstraint(fields=["stage", "item"], name="unique_usage_per_stage_item")]


class ServiceTick(models.Model):
    """تیک «انجام شد» یک خدمت پیش‌فاکتور در مرحله‌ی نصب."""
    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="service_ticks", verbose_name="مرحله‌ی نصب")
    service_line = models.ForeignKey(ProjectService, on_delete=models.CASCADE, related_name="install_ticks", verbose_name="خدمت")
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+", verbose_name="ثبت‌کننده")
    done_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان")

    class Meta:
        verbose_name = "خدمت نصب‌شده"
        verbose_name_plural = "خدمت‌های نصب‌شده"
        constraints = [models.UniqueConstraint(fields=["stage", "service_line"], name="unique_service_tick")]


class StageApproval(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "در انتظار"
        APPROVED = "approved", "تایید شد"
        REJECTED = "rejected", "رد شد"
        CANCELLED = "cancelled", "لغو شد"

    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="approvals", verbose_name="مرحله")
    sent_to_party = models.ForeignKey('core.Party', on_delete=models.PROTECT, related_name="stage_approvals", verbose_name="ارسال‌شده برای")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_approvals", verbose_name="ارسال‌کننده")
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان ارسال")
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING, verbose_name="تصمیم")
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان تصمیم")
    comment = models.TextField(blank=True, verbose_name="توضیح/دلیل رد")

    class Meta:
        verbose_name = "درخواست تاییدیه مرحله"
        verbose_name_plural = "درخواست‌های تاییدیه مرحله"


def project_file_upload_path(instance, filename):
    return f"projects/{instance.stage.project_id}/stage_{instance.stage_id}/{filename}"


class ProjectFile(TimeStampedModel):
    class Kind(models.TextChoices):
        DWG = "dwg", "فایل اتوکد (DWG)"
        GCODE = "gcode", "فایل جی‌کد (برش CNC)"
        PDF = "pdf", "PDF"
        IMAGE = "image", "عکس"
        OTHER = "other", "سایر"

    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="files", verbose_name="مرحله")
    title = models.CharField(max_length=150, blank=True, verbose_name="عنوان فایل")
    file = models.FileField(upload_to=project_file_upload_path, verbose_name="فایل")
    original_name = models.CharField(max_length=255, blank=True, verbose_name="نام اصلی فایل")
    is_attachment = models.BooleanField(default=False, verbose_name="پیوست (بدون نسخه‌بندی)")
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="نوع فایل")
    version = models.PositiveSmallIntegerField(verbose_name="شماره نسخه", blank=True)
    is_current = models.BooleanField(default=True, verbose_name="آخرین نسخه")
    replaces = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by", verbose_name="جایگزین نسخه")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_project_files", verbose_name="آپلودکننده")
    cut_count = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="تعداد برش (فقط جی‌کد)")
    group = models.ForeignKey('FileGroup', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="files", verbose_name="گروه (مثلاً طبقه)")

    @property
    def display_name(self):
        return self.original_name or os.path.basename(self.file.name)

    @property
    def is_displayable_image(self):
        return self.file.name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "gif")

    class Meta:
        verbose_name = "فایل پروژه"
        verbose_name_plural = "فایل‌های پروژه"
        ordering = ["stage", "-version"]

    def save(self, *args, **kwargs):
        if self.is_attachment:   # پیوست‌های چندفایلی نسخه‌ی هم را کنار نمی‌زنند (پنل کامل فایل‌ها: فاز ۲)
            self.version = self.version or 1
            return super().save(*args, **kwargs)
        if not self.version:
            last = ProjectFile.objects.filter(stage=self.stage, kind=self.kind).order_by("-version").first()
            self.version = (last.version + 1) if last else 1
        if self.is_current:
            ProjectFile.objects.filter(stage=self.stage, kind=self.kind, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)


class FileGroup(TimeStampedModel):
    """گروه فایل‌های جی‌کد (مثلاً «طبقه‌ی اول»). در برش‌کاری هر گروه یک تیک «انجام شد» دارد."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="file_groups", verbose_name="پروژه")
    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="file_groups", verbose_name="مرحله‌ی جی‌کد")
    title = models.CharField(max_length=100, verbose_name="نام گروه")
    cut_done = models.BooleanField(default=False, verbose_name="برش این گروه انجام شد")
    cut_done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", verbose_name="ثبت‌کننده‌ی انجام برش")
    cut_done_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان انجام برش")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="سازنده")

    class Meta:
        verbose_name = "گروه فایل"
        verbose_name_plural = "گروه‌های فایل"
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["stage", "title"], name="unique_group_title_per_stage")]

    def __str__(self):
        return self.title





class ProjectCost(models.Model):
    """هزینه‌ی ثبت‌شده‌ی پروژه (مثل ارسال قطعات جدید). روی فاکتور نمی‌آید."""
    class Kind(models.TextChoices):
        LABOR = "labor", "دستمزد"
        TRANSPORT = "transport", "حمل و ایاب‌ذهاب"
        DAMAGE = "damage", "خسارت"
        PART_SHIPPING = "part_shipping", "ارسال قطعات جدید"
        OTHER = "other", "سایر"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="recorded_costs", verbose_name="پروژه")
    kind = models.CharField(max_length=30, choices=Kind.choices, verbose_name="نوع")
    title = models.CharField(max_length=255, verbose_name="شرح")
    amount = models.DecimalField(max_digits=18, decimal_places=0, verbose_name="مبلغ (تومان)")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "هزینه‌ی ثبت‌شده"
        verbose_name_plural = "هزینه‌های ثبت‌شده"
