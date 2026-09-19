from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.contrib import messages
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display, action
from simple_history.admin import SimpleHistoryAdmin
from accounts.models import User
from .forms import StageAdvanceForm
from .models import (
    Project, ProjectService, ProjectMaterial, ProjectParticipant,
    WorkflowTemplate, WorkflowStepTemplate, ProjectStage, StageEvent, StageApproval, ProjectFile,
)


class ProjectServiceInline(TabularInline):
    model = ProjectService
    extra = 0


class ProjectMaterialInline(TabularInline):
    model = ProjectMaterial
    extra = 0


class ProjectParticipantInline(TabularInline):
    model = ProjectParticipant
    extra = 0


@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin, ModelAdmin):
    change_form_before_template = "admin/projects/project/change_form_timeline.html"
    list_display = ('id', 'code', 'name', 'partner', 'owner', 'current_stage_display', 'status', 'contract_date', 'created_at')
    list_filter = ('status', 'contract_date', 'created_at')
    search_fields = ('code', 'name', 'partner__name', 'owner__name')
    filter_horizontal = ('assigned_technicians',)
    raw_id_fields = ('partner', 'owner', 'location', 'created_by')
    readonly_fields = ('code',)
    inlines = [ProjectServiceInline, ProjectMaterialInline, ProjectParticipantInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == User.Role.ADMIN:
            return qs
        if request.user.role == User.Role.EMPLOYEE:
            return qs.filter(
                models.Q(assigned_technicians=request.user) | models.Q(participants__user=request.user)
            ).distinct()
        return qs.none()

    @admin.display(description="مرحله جاری")
    def current_stage_display(self, obj):
        current = obj.stages.filter(status=ProjectStage.Status.IN_PROGRESS).first()
        if current:
            return f"در مرحله: {current.title}"
        done_count = obj.stages.filter(status=ProjectStage.Status.DONE).count()
        total_count = obj.stages.count()
        if total_count > 0 and done_count == total_count:
            return "تکمیل شده"
        return "در انتظار شروع"


class WorkflowStepTemplateInline(TabularInline):
    model = WorkflowStepTemplate
    extra = 0
    fk_name = 'template'


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(ModelAdmin):
    list_display = ('id', 'name', 'is_default')
    inlines = [WorkflowStepTemplateInline]


class StageEventInline(TabularInline):
    model = StageEvent
    extra = 0
    readonly_fields = ('actor', 'from_status', 'to_status', 'comment', 'created_at')


class ProjectFileInline(TabularInline):
    model = ProjectFile
    extra = 0
    readonly_fields = ('version',)


@admin.register(ProjectStage)
class ProjectStageAdmin(ModelAdmin):
    list_display = ('id', 'project', 'title', 'status', 'assigned_to', 'assignment_flag', 'started_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('project__name', 'title')
    raw_id_fields = ('project', 'assigned_to', 'completed_by')
    filter_horizontal = ('candidate_users',)
    inlines = [StageEventInline, ProjectFileInline]
    actions = ['action_claim_for_me', 'action_advance_done', 'action_advance_rejected']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == User.Role.ADMIN:
            return qs
        if request.user.role == User.Role.EMPLOYEE:
            return qs.filter(models.Q(assigned_to=request.user) | models.Q(candidate_users=request.user)).distinct()
        return qs.none()

    @display(description="وضعیت ارجاع", boolean=False)
    def assignment_flag(self, obj):
        if obj.needs_manual_assignment:
            return format_html('<span style="color:#dc2626;font-weight:bold;">⚠ نیازمند تعیین مسئول</span>')
        if obj.assigned_to_id:
            return format_html('<span style="color:#16a34a;">✓ {}</span>', obj.assigned_to.get_full_name() or obj.assigned_to.username)
        return format_html('<span style="color:#d97706;">در استخر ({} کاندیدا)</span>', obj.candidate_users.count())

    @action(description="این کار را برای خودم بردار (Claim)")
    def action_claim_for_me(self, request, queryset):
        from .services import claim_stage
        for stage in queryset:
            try:
                claim_stage(stage, request.user)
            except ValueError as e:
                self.message_user(request, f"{stage}: {e}", level='error')

    @action(
        description="تکمیل و اتمام مرحله",
        dialog={
            "title": "تکمیل مرحله",
            "description": "لطفاً توضیحات و گزارش کار این مرحله را وارد کنید.",
            "form_class": StageAdvanceForm,
        },
    )
    def action_advance_done(self, request, form, object_id):
        from .services import advance_stage
        comment = form.cleaned_data.get("comment")
        stage = ProjectStage.objects.get(pk=object_id)
        try:
            advance_stage(stage, actor=request.user, new_status=ProjectStage.Status.DONE, comment=comment)
            messages.success(request, f"مرحله «{stage.title}» با موفقیت به حالت انجام‌شده تغییر یافت.")
        except ValueError as e:
            messages.error(request, str(e))
        return HttpResponse(headers={"HX-Redirect": reverse_lazy("admin:projects_projectstage_changelist")})

    @action(
        description="رد / نیازمند اصلاح",
        dialog={
            "title": "رد مرحله",
            "description": "لطفاً دلایل و ایرادات این مرحله را وارد کنید.",
            "form_class": StageAdvanceForm,
        },
    )
    def action_advance_rejected(self, request, form, object_id):
        from .services import advance_stage
        comment = form.cleaned_data.get("comment")
        stage = ProjectStage.objects.get(pk=object_id)
        try:
            advance_stage(stage, actor=request.user, new_status=ProjectStage.Status.REJECTED, comment=comment)
            messages.warning(request, f"مرحله «{stage.title}» رد شد و بازگردانده شد.")
        except ValueError as e:
            messages.error(request, str(e))
        return HttpResponse(headers={"HX-Redirect": reverse_lazy("admin:projects_projectstage_changelist")})


@admin.register(StageApproval)
class StageApprovalAdmin(ModelAdmin):
    list_display = ('id', 'stage', 'sent_to_party', 'decision', 'sent_at', 'decided_at')
    list_filter = ('decision',)
