from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from core.models import TimeStampedModel


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

    contract_date = models.DateField(null=True, blank=True, verbose_name="تاریخ عقد قرارداد")
    guaranteed_end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ تضمین پایان قرارداد")
    estimated_end_date = models.DateField(null=True, blank=True, verbose_name="تاریخ تخمینی پایان")
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
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        year = timezone.now().strftime("%y")
        last = Project.objects.filter(code__startswith=f"P{year}-").order_by("-id").first()
        seq = int(last.code.split("-")[-1]) + 1 if last else 1
        return f"P{year}-{seq:04d}"

    @property
    def current_files(self):
        """همه‌ی فایل‌های جاری (آخرین نسخه) پروژه، صرف‌نظر از اینکه در کدام مرحله آپلود شده‌اند."""
        from .models import ProjectFile
        return ProjectFile.objects.filter(stage__project=self, is_current=True).select_related("stage").order_by("kind", "-version")


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
    responsible_role = models.CharField(max_length=20, choices=[('manager', 'مدیر'), ('employee', 'تکنسین')], blank=True, verbose_name="نقش مسئول")
    responsible_specialty = models.ForeignKey('core.Specialty', null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_steps", verbose_name="تخصص مورد نیاز")
    approval_by = models.CharField(max_length=20, choices=ApprovalBy.choices, default=ApprovalBy.NONE, verbose_name="نیازمند تایید توسط")
    estimated_duration_hours = models.PositiveIntegerField(null=True, blank=True, verbose_name="مدت‌زمان تخمینی (ساعت)")
    client_visible = models.BooleanField(default=True, verbose_name="قابل نمایش به کارفرما")
    allows_file_upload = models.BooleanField(default=False, verbose_name="امکان آپلود فایل در این مرحله")
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

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="stages", verbose_name="پروژه")
    step_template = models.ForeignKey(WorkflowStepTemplate, on_delete=models.PROTECT, related_name="stage_instances", verbose_name="مرحله قالب مرجع")
    order = models.PositiveSmallIntegerField(verbose_name="ترتیب")
    title = models.CharField(max_length=150, verbose_name="عنوان مرحله (کپی‌شده)")
    client_label = models.CharField(max_length=150, blank=True, verbose_name="عنوان نمایشی برای کارفرما")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name="وضعیت")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_stages", verbose_name="مسئول انجام")
    candidate_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="candidate_stages",
        verbose_name="افراد واجد شرایط (تا زمانی که کسی کار را برندارد)",
    )
    client_visible = models.BooleanField(default=True, verbose_name="قابل نمایش به کارفرما")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان شروع")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="زمان اتمام")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_stages", verbose_name="انجام‌دهنده")
    rejection_count = models.PositiveSmallIntegerField(default=0, verbose_name="تعداد دفعات رد شدن")

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


class StageEvent(models.Model):
    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="events", verbose_name="مرحله")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="stage_events", verbose_name="انجام‌دهنده")
    from_status = models.CharField(max_length=20, blank=True, verbose_name="وضعیت قبلی")
    to_status = models.CharField(max_length=20, verbose_name="وضعیت جدید")
    comment = models.TextField(blank=True, verbose_name="توضیح")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="زمان")

    class Meta:
        verbose_name = "رویداد مرحله"
        verbose_name_plural = "رویدادهای مرحله"
        ordering = ["created_at"]


class StageApproval(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "در انتظار"
        APPROVED = "approved", "تایید شد"
        REJECTED = "rejected", "رد شد"

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
        PDF = "pdf", "PDF"
        IMAGE = "image", "عکس"
        OTHER = "other", "سایر"

    stage = models.ForeignKey(ProjectStage, on_delete=models.CASCADE, related_name="files", verbose_name="مرحله")
    title = models.CharField(max_length=150, blank=True, verbose_name="عنوان فایل")
    file = models.FileField(upload_to=project_file_upload_path, verbose_name="فایل")
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="نوع فایل")
    version = models.PositiveSmallIntegerField(verbose_name="شماره نسخه", blank=True)
    is_current = models.BooleanField(default=True, verbose_name="آخرین نسخه")
    replaces = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by", verbose_name="جایگزین نسخه")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="uploaded_project_files", verbose_name="آپلودکننده")

    class Meta:
        verbose_name = "فایل پروژه"
        verbose_name_plural = "فایل‌های پروژه"
        ordering = ["stage", "-version"]

    def save(self, *args, **kwargs):
        if not self.version:
            last = ProjectFile.objects.filter(stage=self.stage, kind=self.kind).order_by("-version").first()
            self.version = (last.version + 1) if last else 1
        if self.is_current:
            ProjectFile.objects.filter(stage=self.stage, kind=self.kind, is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)
