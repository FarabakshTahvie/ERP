from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from simple_history.admin import SimpleHistoryAdmin
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
    actions = ['action_claim_for_me']

    @admin.display(description="وضعیت ارجاع", boolean=False)
    def assignment_flag(self, obj):
        if obj.needs_manual_assignment:
            return format_html('<span style="color:#dc2626;font-weight:bold;">⚠ نیازمند تعیین مسئول</span>')
        if obj.assigned_to_id:
            return format_html('<span style="color:#16a34a;">✓ {}</span>', obj.assigned_to.get_full_name() or obj.assigned_to.username)
        return format_html('<span style="color:#d97706;">در استخر ({} کاندیدا)</span>', obj.candidate_users.count())

    @admin.action(description="این کار را برای خودم بردار (Claim)")
    def action_claim_for_me(self, request, queryset):
        from .services import claim_stage
        for stage in queryset:
            try:
                claim_stage(stage, request.user)
            except ValueError as e:
                self.message_user(request, f"{stage}: {e}", level='error')


@admin.register(StageApproval)
class StageApprovalAdmin(ModelAdmin):
    list_display = ('id', 'stage', 'sent_to_party', 'decision', 'sent_at', 'decided_at')
    list_filter = ('decision',)
