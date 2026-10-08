from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

NEXT_PARAM = "next"
MAX_NEXT = 800

# صفحه‌های ریشه: دکمه‌ی برگشت ندارند
TOP_LEVEL = {"home", "dashboard:overview", "projects:my_tasks", "accounts:login", "accounts:force_set_password"}

# نام صفحه ← (نام والد، [نام kwargهای والد که از kwargهای همین صفحه می‌آیند]، {query ثابت})
PAGE_PARENTS = {
    "accounts:register_staff": ("people:staff", [], {}),
    "accounts:password_reset_request": ("accounts:login", [], {}),
    "accounts:change_password": ("home", [], {}),
    "dashboard:stages": ("dashboard:overview", [], {}),
    "dashboard:assign_stage": ("dashboard:stages", [], {}),
    "dashboard:suspended": ("dashboard:overview", [], {}),
    "dashboard:held_detail": ("dashboard:suspended", [], {}),
    "dashboard:notifications": ("dashboard:overview", [], {}),
    "dashboard:notification_detail": ("dashboard:notifications", [], {}),
    "people:staff": ("home", [], {}),
    "people:customers": ("home", [], {}),
    "people:user_detail": ("people:staff", [], {}),
    "people:user_edit": ("people:user_detail", ["user_id"], {}),
    "people:user_reset_password": ("people:user_detail", ["user_id"], {}),
    "people:party_detail": ("people:customers", [], {}),
    "people:party_edit": ("people:party_detail", ["party_id"], {}),
    "tasks:list": ("home", [], {}),
    "tasks:detail": ("tasks:list", [], {}),
    "tasks:edit": ("tasks:detail", ["task_id"], {}),
    "inventory:item_new": ("home", [], {"tab": "stock"}),
    "inventory:item_edit": ("home", [], {"tab": "stock"}),
    "inventory:purchase_new": ("home", [], {}),
    "inventory:stock_movement_new": ("home", [], {}),
    "inventory:bulk_opening": ("home", [], {}),
    "inventory:bulk_reconciliation": ("home", [], {}),
    "notifications:center": ("home", [], {}),
    "notifications:broadcast_form": ("home", [], {}),
    "notifications:broadcast_preview": ("notifications:broadcast_form", [], {}),
    "notifications:broadcast_history": ("notifications:broadcast_form", [], {}),
    "notifications:broadcast_detail": ("notifications:broadcast_history", [], {}),
    "projects:staff_project_overview": ("home", [], {}),
    "projects:project_edit": ("projects:staff_project_overview", ["project_id"], {}),
    "projects:proforma_editor": ("projects:staff_project_overview", ["project_id"], {}),
    "projects:final_review": ("projects:staff_project_overview", ["project_id"], {}),
    "projects:part_request_detail": ("home", [], {"tab": "part_requests"}),
    "projects:my_task_detail": ("home", [], {}),
    "projects:new_project_form": ("home", [], {}),
    "projects:portal_stage_approval": ("home", [], {}),
    "projects:portal_project_progress": ("home", [], {}),
    "finance:accounting_overview": ("home", [], {}),
    "finance:accounting_projects": ("finance:accounting_overview", [], {}),
    "finance:accounting_project": ("finance:accounting_projects", [], {}),
    "finance:accounting_stock": ("finance:accounting_overview", [], {}),
    "finance:accounting_purchases": ("finance:accounting_overview", [], {}),
    "finance:accounting_suppliers": ("finance:accounting_overview", [], {}),
    "finance:accounting_supplier": ("finance:accounting_suppliers", [], {}),
    "finance:accounting_periods": ("finance:accounting_overview", [], {}),
    "finance:accounting_reports": ("finance:accounting_overview", [], {}),
    "finance:accounting_customers": ("finance:accounting_overview", [], {}),
    "finance:payments_review": ("home", [], {}),
    "finance:payment_detail": ("finance:payments_review", [], {}),
    "finance:portal_invoice_detail": ("home", [], {}),
    "finance:portal_add_payment": ("finance:portal_invoice_detail", ["invoice_uuid"], {}),
    "finance:portal_statement": ("home", [], {}),
}

# صفحه‌های چندورودی؛ لینک به آن‌ها باید ?next بگیرد.
MULTI_ENTRY = {
    "projects:staff_project_overview", "finance:accounting_project", "finance:payment_detail",
    "finance:portal_invoice_detail", "people:user_detail", "people:party_detail",
    "projects:final_review", "projects:portal_stage_approval", "notifications:broadcast_detail",
}

# هر نام URL پروژه که نه صفحه است و نه ریشه (POST، JSON، جزء htmx، فایل، ریدایرکت)
NON_PAGE = {
    "accounts:logout", "accounts:otp_phone_form", "accounts:password_reset_verify",
    "accounts:pwreset_phone_form", "accounts:request_otp_login", "accounts:verify_otp_login",
    "dashboard:cancelled_table", "dashboard:notification_resend", "dashboard:notifications_table",
    "dashboard:project_restore", "dashboard:projects_table", "dashboard:stage_suspend",
    "dashboard:stages_table", "dashboard:suspended_cancel", "dashboard:suspended_resume",
    "dashboard:suspended_table", "finance:accounting_add_cost", "finance:accounting_add_payment",
    "finance:accounting_adjust_invoice", "finance:accounting_cancel_invoice",
    "finance:accounting_delete_cost", "finance:accounting_period_toggle",
    "finance:accounting_projects_table", "finance:accounting_purchases_table",
    "finance:accounting_set_due", "finance:accounting_stock_table", "finance:accounting_suppliers_table",
    "finance:payment_decide", "finance:payments_table", "finance:portal_invoice_pdf",
    "inventory:bulk_template", "inventory:item_quick_create", "inventory:item_toggle_active",
    "inventory:stock_table", "manifest", "najva_sw", "notifications:broadcast_detail_table",
    "notifications:broadcast_history_table", "notifications:broadcast_retry",
    "notifications:mark_all_seen", "notifications:track_click", "people:customers_table",
    "people:search", "people:staff_table", "people:user_toggle_active", "projects:cut_set",
    "projects:dashboard_claimable_table", "projects:dashboard_completed_table",
    "projects:dashboard_my_projects_table", "projects:dashboard_my_tasks_table",
    "projects:extra_add", "projects:extra_delete", "projects:final_review_consume",
    "projects:install_line", "projects:move_stage", "projects:my_task_claim",
    "projects:my_task_complete", "projects:my_task_transfer", "projects:new_project_party_search",
    "projects:new_project_submit", "projects:part_request_cancel", "projects:part_request_create",
    "projects:part_request_decide", "projects:part_requests_table", "projects:portal_stage_file",
    "projects:ship_check", "projects:stage_file_upload", "protected_media",
    "tasks:attachment_delete", "tasks:attachment_upload", "tasks:check", "tasks:done_panel",
    "tasks:done_table", "tasks:my_panel", "tasks:open_table", "tasks:save", "tasks:submit",
    "utils:dev_test_calendar", "utils:dev_test_design_system", "utils:dev_test_map",
    "utils:register_push_device",
    "messenger:api_inbox", "messenger:api_open", "messenger:api_messages", "messenger:api_send",
    "messenger:api_read", "messenger:api_mute", "messenger:api_edit", "messenger:api_delete",
}


def safe_internal_path(request, value):
    """مسیر داخلی امن یا None. فقط مسیر نسبی، بدون دامنه/طرح/بک‌اسلش/کاراکتر کنترلی، و قابل resolve."""
    if not value or len(value) > MAX_NEXT or not value.startswith("/") or value.startswith("//"):
        return None
    if "\\" in value or any(ord(c) < 32 for c in value):
        return None
    if not url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return None
    try:
        resolve(urlsplit(value).path)
    except Resolver404:
        return None
    return value


def _strip_next(url):
    parts = urlsplit(url)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != NEXT_PARAM]
    return parts.path + (("?" + urlencode(pairs)) if pairs else "")


def current_page_url(request):
    """آدرس «صفحه‌ی میزبان» بدون پارامتر next خودش.
    برای درخواست htmx همان HX-Current-URL است (نه آدرس اندپوینت جدول)."""
    if request.headers.get("HX-Request"):
        raw = request.headers.get("HX-Current-URL")
        if raw:
            parts = urlsplit(raw)
            if parts.netloc == request.get_host():
                candidate = parts.path + (f"?{parts.query}" if parts.query else "")
                if safe_internal_path(request, candidate):
                    return _strip_next(candidate)
    return _strip_next(request.get_full_path())


def with_next(request, url):
    """url را با ?next=<صفحه‌ی فعلی> برمی‌گرداند (برای لینک به صفحه‌ی چندورودی)."""
    here = current_page_url(request)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{NEXT_PARAM}={quote(here, safe='')}"


def nav_reverse(request, name, args=(), kwargs=None):
    return with_next(request, reverse(name, args=list(args), kwargs=kwargs))


def _parent_url(spec, kwargs):
    name, kw_names, query = spec
    url = reverse(name, kwargs={k: kwargs[k] for k in kw_names})
    return url + (("?" + urlencode(query)) if query else "")


def resolve_back(request):
    """آدرس دکمه‌ی برگشت یا None (صفحه‌ی ریشه). هرگز استثنا نمی‌دهد."""
    try:
        match = request.resolver_match
        if match is None or match.view_name in TOP_LEVEL:
            return None
        candidate = safe_internal_path(request, request.GET.get(NEXT_PARAM))
        if candidate and urlsplit(candidate).path != request.path:
            return candidate
        spec = PAGE_PARENTS.get(match.view_name)
        return _parent_url(spec, match.kwargs) if spec else reverse("home")
    except Exception:
        return None
