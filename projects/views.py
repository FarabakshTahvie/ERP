from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import models as dj_models, transaction
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
import json
from decimal import Decimal, InvalidOperation
from utils.generic_table import build_table_context
from utils.jalali import jalali_str, to_fa_digits
from accounts.models import User
from core.models import Party
from catalog.models import Service, Item
from .models import Project, ProjectStage, StageApproval
from .services import (
    claim_stage, advance_stage, transfer_stage, get_transfer_candidates,
    create_project_from_technician_intake, user_can_create_projects,
    decide_stage_approval, can_edit_project, project_prices_editable,
    update_project_from_technician_edit, EDITABLE_PROJECT_STATUSES,
    stage_approval_action,
)
from finance.services import create_customer_payment


def _parse_json_lines(raw_value):
    """پارس امن services_json/materials_json — اگر یکی خالی/نامعتبر بود، آن‌یکی را خراب نمی‌کند."""
    try:
        data = json.loads(raw_value) if raw_value else []
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_lines_strict(raw_value):
    """برای ویرایش: None یعنی «ارسال نشده». JSON خراب خطا می‌دهد، نه لیست خالی (که ردیف‌ها را پاک می‌کرد)."""
    if raw_value is None:
        return None
    try:
        data = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        raise ValueError("اطلاعات ردیف‌ها نامعتبر است؛ صفحه را دوباره باز کنید.")
    if not isinstance(data, list):
        raise ValueError("اطلاعات ردیف‌ها نامعتبر است؛ صفحه را دوباره باز کنید.")
    return data


def _line_choices(project):
    """خدمات/کالاهای قابل انتخاب + موارد فعلی پروژه (حتی اگر بعداً غیرفعال شده باشند)."""
    services = list(Service.objects.filter(is_active=True).exclude(children__isnull=False))
    used = set(project.services.values_list("service_id", flat=True)) - {s.id for s in services}
    if used:
        services += list(Service.objects.filter(pk__in=used))
    items = list(Item.objects.filter(is_active=True))
    used = set(project.extra_materials.values_list("item_id", flat=True)) - {i.id for i in items}
    if used:
        items += list(Item.objects.filter(pk__in=used))
    return services, items


def _initial_lines(project):
    def qty_str(value):
        return format(value.normalize(), "f")
    return {
        "services": [
            {"pk": ps.pk, "id": ps.service_id, "qty": qty_str(ps.qty), "unit_price": str(int(ps.unit_price))}
            for ps in project.services.order_by("pk")
        ],
        "materials": [
            {"pk": pm.pk, "id": pm.item_id, "qty": qty_str(pm.qty), "unit_price": str(int(pm.unit_price))}
            for pm in project.extra_materials.order_by("pk")
        ],
    }


DURATION_HINTS = {
    range(0, 5): "معمولاً چند ساعت طول می‌کشد.",
    range(5, 17): "معمولاً یک روز کاری طول می‌کشد.",
    range(17, 49): "معمولاً دو تا سه روز کاری طول می‌کشد.",
}


def _is_technician(user):
    return user.is_authenticated and user.role == User.Role.EMPLOYEE


def _duration_hint(hours):
    if not hours:
        return ""
    for r, text in DURATION_HINTS.items():
        if hours in r:
            return text
    return "ممکن است چند روز طول بکشد."


def technician_home_view(request, user):
    can_create = user_can_create_projects(user)

    my_stages_count = ProjectStage.objects.filter(status=ProjectStage.Status.IN_PROGRESS, assigned_to=user).count()
    pool_stages_count = ProjectStage.objects.filter(
        status=ProjectStage.Status.IN_PROGRESS, candidate_users=user
    ).exclude(assigned_to=user).distinct().count()
    my_projects_count = Project.objects.filter(created_by=user).count() if can_create else 0

    from finance.models import Payment
    pending_payments_count = 0
    if can_create or user.is_superuser or user.role == User.Role.ADMIN:
        pending_qs = Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY)
        if not (user.is_superuser or user.role == User.Role.ADMIN):
            pending_qs = pending_qs.filter(invoice__project__created_by=user)
        pending_payments_count = pending_qs.count()

    return render(request, "projects/technician_home.html", {
        "can_create_projects": can_create,
        "can_review_payments": can_create or user.is_superuser or user.role == User.Role.ADMIN,
        "my_stages_count": my_stages_count,
        "pool_stages_count": pool_stages_count,
        "my_projects_count": my_projects_count,
        "pending_payments_count": pending_payments_count,
    })


@login_required
@user_passes_test(_is_technician)
def dashboard_my_tasks_table(request):
    qs = ProjectStage.objects.filter(
        status=ProjectStage.Status.IN_PROGRESS, assigned_to=request.user
    ).select_related("project", "step_template").order_by("project__name", "order")

    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]),
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "badge", "value": "در حال انجام", "variant": "info"},
            ],
        }

    context = build_table_context(
        request, qs,
        columns=[{"label": "پروژه"}, {"label": "مرحله"}, {"label": "وضعیت"}],
        row_builder=row_builder,
        container_id="table-my-tasks",
        param_prefix="mt_",
        empty_icon="check-circle", empty_text="فعلاً کار فعالی برای شما ثبت نشده.",
        list_url=reverse("projects:dashboard_my_tasks_table"),
    )
    return render(request, "utils/partials/generic_table.html", context)


@login_required
@user_passes_test(_is_technician)
def dashboard_claimable_table(request):
    qs = ProjectStage.objects.filter(
        status=ProjectStage.Status.IN_PROGRESS, candidate_users=request.user
    ).exclude(assigned_to=request.user).select_related("project", "step_template").distinct().order_by("project__name", "order")

    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]),
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "badge", "value": "بدون مسئول ثابت", "variant": "warning"},
            ],
        }

    context = build_table_context(
        request, qs,
        columns=[{"label": "پروژه"}, {"label": "مرحله"}, {"label": "وضعیت"}],
        row_builder=row_builder,
        container_id="table-claimable",
        param_prefix="cl_",
        empty_icon="folder-kanban", empty_text="فعلاً کاری در استخر قابل‌برداشتن نیست.",
        list_url=reverse("projects:dashboard_claimable_table"),
    )
    return render(request, "utils/partials/generic_table.html", context)


@login_required
@user_passes_test(_is_technician)
def dashboard_completed_table(request):
    qs = ProjectStage.objects.filter(
        status=ProjectStage.Status.DONE, completed_by=request.user
    ).select_related("project", "step_template").order_by("-completed_at")

    def row_builder(stage):
        return {
            "url": reverse("projects:my_task_detail", args=[stage.id]) if stage.assigned_to_id == request.user.id else None,
            "cells": [
                {"type": "text", "value": stage.project.name},
                {"type": "text", "value": stage.client_label or stage.title},
                {"type": "muted", "value": jalali_str(stage.completed_at, fmt="%Y/%m/%d %H:%M")},
                {"type": "badge", "value": "تکمیل شد", "variant": "success"},
            ],
        }

    context = build_table_context(
        request, qs,
        columns=[{"label": "پروژه"}, {"label": "مرحله"}, {"label": "تاریخ تکمیل"}, {"label": "وضعیت"}],
        row_builder=row_builder,
        container_id="table-completed",
        param_prefix="dn_",
        empty_icon="check-circle", empty_text="هنوز هیچ کاری را تکمیل نکرده‌اید.",
        list_url=reverse("projects:dashboard_completed_table"),
    )
    return render(request, "utils/partials/generic_table.html", context)


@login_required
@user_passes_test(user_can_create_projects)
def dashboard_my_projects_table(request):
    qs = Project.objects.filter(created_by=request.user).order_by("-created_at")

    def row_builder(project):
        total = project.stages.count()
        done = project.stages.filter(status=ProjectStage.Status.DONE).count()
        percent = int((done / total) * 100) if total else 0
        status_variant = {"completed": "success", "cancelled": "error", "in_progress": "info"}.get(project.status, "neutral")
        return {
            "url": reverse("projects:staff_project_overview", args=[project.id]),
            "cells": [
                {"type": "text", "value": project.name},
                {"type": "muted", "value": to_fa_digits(project.code)},
                {"type": "muted", "value": to_fa_digits(f"{percent}٪")},
                {"type": "badge", "value": project.get_status_display(), "variant": status_variant},
            ],
        }

    context = build_table_context(
        request, qs,
        columns=[{"label": "پروژه"}, {"label": "کد"}, {"label": "پیشرفت"}, {"label": "وضعیت"}],
        row_builder=row_builder,
        container_id="table-my-projects",
        param_prefix="pr_",
        empty_icon="folder-kanban", empty_text="هنوز پروژه‌ای ثبت نکرده‌اید.",
        list_url=reverse("projects:dashboard_my_projects_table"),
    )
    return render(request, "utils/partials/generic_table.html", context)


def _render_staff_project_view(request, project, highlight_stage_id=None):
    """
    یک صفحه‌ی واحد برای «مشاهده‌ی پروژه»: هم تکنسینِ ثبت‌کننده/مسئولان پروژه، هم تکنسین‌هایی
    که یک مرحله را برداشته‌اند یا کاندیدای آن هستند، از همین تابع/تمپلیت استفاده می‌کنند تا
    اطلاعات نمایش‌داده‌شده (اطلاعات تماس، آدرس، فایل‌ها، روند کامل مراحل) یکسان باشد؛ فقط
    دکمه‌های اکشن (برداشتن/تکمیل/انتقال) بسته به اینکه کاربر برای کدام مرحله مسئول یا
    کاندیدا است، نمایش داده می‌شوند.
    """
    user = request.user
    is_project_level_viewer = (
        user.is_superuser or user.role == User.Role.ADMIN
        or project.created_by_id == user.id
        or project.assigned_technicians.filter(pk=user.id).exists()
        or project.participants.filter(user=user).exists()
    )

    stages = list(
        project.stages.select_related("assigned_to", "step_template")
        .prefetch_related("events__actor", "candidate_users")
        .order_by("order")
    )

    my_stage_ids = set()
    for s in stages:
        candidate_ids = {u.id for u in s.candidate_users.all()}
        s.is_mine = s.assigned_to_id == user.id
        s.is_candidate = user.id in candidate_ids
        s.candidate_count = len(candidate_ids)
        if s.is_mine or s.is_candidate:
            my_stage_ids.add(s.id)
        s.transfer_candidates = get_transfer_candidates(s) if s.is_mine else None

    if not is_project_level_viewer and not my_stage_ids:
        raise Http404

    return render(request, "projects/staff_project_overview.html", {
        "project": project, "stages": stages, "highlight_stage_id": highlight_stage_id,
        "can_edit": can_edit_project(user, project) and project.status in EDITABLE_PROJECT_STATUSES,
    })


@login_required
def staff_project_overview(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    return _render_staff_project_view(request, project)


@login_required
def portal_stage_approval(request, approval_id):
    from finance.services import create_customer_payment

    approval = get_object_or_404(
        StageApproval.objects.select_related("stage__project", "stage__step_template", "sent_to_party"),
        pk=approval_id,
    )
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or party.id != approval.sent_to_party_id):
        raise Http404

    stage = approval.stage
    invoice = getattr(stage.project, "invoice", None)
    needs_payment = stage.step_template.requires_payment_selection

    def render_page(**extra):
        ctx = {"approval": approval, "stage": stage, "invoice": invoice, "needs_payment": needs_payment}
        ctx.update(extra)
        return render(request, "projects/portal_stage_approval.html", ctx)

    def finish():
        return redirect("finance:portal_invoice_detail", invoice.uuid) if invoice else redirect("home")

    if approval.decision != StageApproval.Decision.PENDING:
        return render_page(already_decided=True)

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "").strip()

        if action == "reject":
            if not comment:
                messages.error(request, "برای رد، ذکر دلیل اجباری است.")
                return render_page()
            with transaction.atomic():
                locked = StageApproval.objects.select_for_update().get(pk=approval.pk)
                if locked.decision != StageApproval.Decision.PENDING:
                    messages.info(request, "این درخواست قبلاً بررسی شده است.")
                    return finish()
                decide_stage_approval(locked, actor=request.user, decision=StageApproval.Decision.REJECTED, comment=comment)
            messages.success(request, "پاسخ شما ثبت شد.")
            return finish()

        if action == "approve":
            if needs_payment and invoice and request.POST.get("seen_total") != str(int(invoice.total_amount)):
                messages.warning(request, "مبلغ فاکتور از زمان باز شدن این صفحه تغییر کرده است. مبلغ جدید را بررسی کنید و دوباره تایید بزنید.")
                return redirect("projects:portal_stage_approval", approval.id)
            try:
                with transaction.atomic():
                    locked = StageApproval.objects.select_for_update().get(pk=approval.pk)
                    if locked.decision != StageApproval.Decision.PENDING:
                        messages.info(request, "این درخواست قبلاً بررسی شده است.")
                        return finish()
                    if needs_payment and invoice:
                        create_customer_payment(
                            invoice=invoice,
                            method=request.POST.get("payment_method"),
                            amount_raw=request.POST.get("payment_amount"),
                            reference_number=request.POST.get("reference_number", ""),
                            note=comment,
                            receipt_file=request.FILES.get("receipt_file"),
                            cheque_number=request.POST.get("cheque_number", ""),
                            cheque_bank=request.POST.get("cheque_bank", ""),
                        )
                    decide_stage_approval(
                        locked, actor=request.user, decision=StageApproval.Decision.APPROVED,
                        comment=comment or "تایید شد توسط طرف‌حساب",
                    )
            except ValueError as e:
                messages.error(request, str(e))
                return render_page()
            messages.success(request, "تایید شما با موفقیت ثبت شد.")
            return finish()

    return render_page()


@login_required
def project_progress(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    party = getattr(request.user, "party", None)
    if not party or party.id not in (project.partner_id, project.owner_id):
        raise Http404

    invoice = getattr(project, "invoice", None)
    stages = []
    for s in project.stages.filter(client_visible=True).select_related("step_template").order_by("order"):
        action_url, action_label = stage_approval_action(s, invoice)
        stages.append({
            "title": s.client_label or s.title,
            "status": s.status,
            "hint": _duration_hint(s.step_template.estimated_duration_hours),
            "action_url": action_url,
            "action_label": action_label,
        })
    return render(request, "projects/portal_progress.html", {"project": project, "stages": stages})


def _is_technician(user):
    return user.is_authenticated and user.role == User.Role.EMPLOYEE


def _technician_stage_qs(user):
    return ProjectStage.objects.filter(
        status=ProjectStage.Status.IN_PROGRESS,
    ).filter(
        dj_models.Q(assigned_to=user) | dj_models.Q(candidate_users=user)
    ).select_related("project", "step_template").distinct().order_by("project__name", "order")


@login_required
@user_passes_test(_is_technician)
def my_tasks(request):
    return redirect("home")


@login_required
@user_passes_test(_is_technician)
def my_task_detail(request, stage_id):
    stage = get_object_or_404(ProjectStage.objects.select_related("project"), pk=stage_id)
    is_mine = stage.assigned_to_id == request.user.id
    is_candidate = stage.candidate_users.filter(pk=request.user.id).exists()
    if not is_mine and not is_candidate:
        raise Http404
    return _render_staff_project_view(request, stage.project, highlight_stage_id=stage.id)


@login_required
@user_passes_test(_is_technician)
def my_task_claim(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    try:
        claim_stage(stage, request.user)
        messages.success(request, "کار با موفقیت برداشته شد.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@user_passes_test(_is_technician)
def my_task_complete(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()
        if stage.step_template.allows_file_upload and not request.FILES.get("uploaded_file"):
            messages.error(request, "برای این مرحله آپلود فایل الزامی است.")
            return redirect("projects:my_task_detail", stage_id=stage.id)
        try:
            advance_stage(stage, actor=request.user, new_status=ProjectStage.Status.DONE, comment=comment)
            uploaded_file = request.FILES.get("uploaded_file")
            if uploaded_file:
                from .models import ProjectFile
                from utils.utils import guess_file_kind
                ProjectFile.objects.create(
                    stage=stage, file=uploaded_file,
                    kind=guess_file_kind(uploaded_file.name),
                    uploaded_by=request.user,
                )
            messages.success(request, "مرحله با موفقیت تکمیل شد.")
            return redirect("home")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@user_passes_test(_is_technician)
def my_task_transfer(request, stage_id):
    stage = get_object_or_404(ProjectStage, pk=stage_id)
    if request.method == "POST":
        target_user = User.objects.filter(pk=request.POST.get("target_user")).first()
        comment = request.POST.get("comment", "").strip()
        if not target_user:
            messages.error(request, "تکنسین انتخاب‌شده معتبر نیست.")
        else:
            try:
                transfer_stage(stage, from_user=request.user, to_user=target_user, comment=comment)
                messages.success(request, f"کار به {target_user.get_full_name() or target_user.username} منتقل شد.")
                return redirect("home")
            except ValueError as e:
                messages.error(request, str(e))
    return redirect("projects:my_task_detail", stage_id=stage.id)


@login_required
@user_passes_test(user_can_create_projects)
def new_project_form(request):
    services = Service.objects.filter(is_active=True).exclude(children__isnull=False)
    items = Item.objects.filter(is_active=True)
    return render(request, "projects/technician_new_project.html", {"services": services, "items": items})


@login_required
@user_passes_test(user_can_create_projects)
def new_project_party_search(request):
    phone = request.GET.get("phone_number", "").strip()
    prefix = request.GET.get("prefix", "")
    party = Party.objects.filter(phone_number=phone).first() if phone else None
    return render(request, "projects/partials/technician_party_search_result.html", {
        "phone_number": phone, "party": party, "prefix": prefix,
    })


@login_required
def project_edit(request, project_id):
    project = get_object_or_404(Project.objects.select_related("location", "partner", "owner"), pk=project_id)
    if not can_edit_project(request.user, project):
        raise Http404
    if project.status not in EDITABLE_PROJECT_STATUSES:
        messages.error(request, "پروژه‌ی تکمیل‌شده یا لغوشده قابل ویرایش نیست.")
        return redirect("projects:staff_project_overview", project.id)

    if request.method == "POST":
        try:
            project, rebuilt = update_project_from_technician_edit(
                project=project, actor=request.user,
                location_lat=request.POST.get("latitude") or None,
                location_lng=request.POST.get("longitude") or None,
                location_address=request.POST.get("address_text", ""),
                service_lines=_parse_json_lines_strict(request.POST.get("services_json")),
                material_lines=_parse_json_lines_strict(request.POST.get("materials_json")),
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:project_edit", project.id)
        messages.success(request, "تغییرات ذخیره شد و پیش‌فاکتور با مبلغ جدید بازتولید شد." if rebuilt else "تغییرات ذخیره شد.")
        return redirect("projects:staff_project_overview", project.id)

    location = project.location
    services, items = _line_choices(project)
    return render(request, "projects/technician_edit_project.html", {
        "project": project,
        "prices_open": project_prices_editable(project),
        "services": services, "items": items, "initial_lines": _initial_lines(project),
        "lat": str(location.latitude) if location and location.latitude is not None else "",
        "lng": str(location.longitude) if location and location.longitude is not None else "",
        "address_text": location.address_text if location else "",
    })


@login_required
@user_passes_test(user_can_create_projects)
def new_project_submit(request):
    if request.method != "POST":
        return redirect("projects:new_project_form")

    party_id = request.POST.get("party_id") or None
    party_data = None
    if not party_id:
        roles = request.POST.getlist("roles")
        if not roles:
            messages.error(request, "لطفاً حداقل یک نقش (کارفرما، شریک تجاری، پیمانکار یا تأمین‌کننده) را برای طرف‌حساب انتخاب کنید.")
            return redirect("projects:new_project_form")
        party_data = {
            "name": request.POST.get("party_name", "").strip(),
            "brand_name": request.POST.get("brand_name", "").strip(),
            "entity_type": request.POST.get("entity_type", "individual"),
            "phone_number": request.POST.get("phone_number", "").strip(),
            "national_code": request.POST.get("national_code", "").strip() or None,
            "is_partner": "partner" in roles,
            "is_client": "client" in roles,
            "is_contractor": "contractor" in roles,
            "is_supplier": "supplier" in roles,
        }

    owner_party_id = None
    owner_party_data = None
    if request.POST.get("different_owner") == "on":
        owner_party_id = request.POST.get("owner_party_id") or None
        if not owner_party_id:
            owner_party_data = {
                "name": request.POST.get("owner_party_name", "").strip(),
                "brand_name": request.POST.get("owner_brand_name", "").strip(),
                "entity_type": request.POST.get("owner_entity_type", "individual"),
                "phone_number": request.POST.get("owner_phone_number", "").strip(),
                "national_code": request.POST.get("owner_national_code", "").strip() or None,
                "is_client": True,
            }
            if not owner_party_data["phone_number"]:
                messages.error(request, "شماره‌ی صاحب ملک/کارفرما را وارد کنید یا تیک «صاحب ملک شخص دیگری است» را بردارید.")
                return redirect("projects:new_project_form")

    service_lines = _parse_json_lines(request.POST.get("services_json"))
    material_lines = _parse_json_lines(request.POST.get("materials_json"))

    try:
        project, invoice, account_conflict = create_project_from_technician_intake(
            created_by=request.user,
            party_id=party_id, party_data=party_data,
            owner_party_id=owner_party_id, owner_party_data=owner_party_data,
            location_lat=request.POST.get("latitude") or None,
            location_lng=request.POST.get("longitude") or None,
            location_address=request.POST.get("address_text", ""),
            service_lines=service_lines, material_lines=material_lines,
            send_sms=request.POST.get("send_sms") == "on",
        )
        messages.success(request, f"پروژه «{project.name}» با موفقیت ثبت شد.")
        if account_conflict:
            messages.warning(request, "این شماره موبایل قبلاً برای یک حساب کاربری دیگر (مثلاً یکی از پرسنل) ثبت شده؛ برای این طرف‌حساب حساب ورود خودکار ساخته نشد. برای دسترسی به پرتال، از پنل ادمین دستی برایش حساب بسازید.")
        return redirect("home")
    except (ValueError, InvalidOperation) as e:
        messages.error(request, str(e))
        return redirect("projects:new_project_form")
