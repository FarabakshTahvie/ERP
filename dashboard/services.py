from datetime import timedelta

import jdatetime
from django.db.models import Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from core.models import PeriodLock
from core.periods import current_ym, month_label
from finance import accounting
from finance.models import Invoice, Payment
from inventory.services import low_stock_items_count
from notifications.models import Notification
from projects.models import PartRequest, Project, ProjectStage, StageApproval, StageEvent
from utils.jalali import to_fa_digits
from utils.utils import separate_digits

STALE_STAGE_DAYS = 3
SLOW_APPROVAL_DAYS = 2
OVERDUE_INVOICE_DAYS = 30
FAILED_NOTIFICATION_DAYS = 7
LIST_LIMIT = 6
MONEY = DecimalField(max_digits=24, decimal_places=2)
_LEVEL_RANK = {"error": 0, "warning": 1, "info": 2}
_LIVE = {"project__status": Project.Status.IN_PROGRESS}


def _fa(value):
    return to_fa_digits(value)


def _since(dt, now):
    return max((now - dt).days, 0) if dt else 0


def _project_url(project_id):
    return reverse("projects:staff_project_overview", args=[project_id])


def _stage_row(stage, now, since=None, extra=""):
    days = _since(since or stage.started_at, now)
    sub = _fa(f"{days} روز") + (f" — {extra}" if extra else "")
    return {"title": f"{stage.project.name} — {stage.title}", "sub": sub, "url": _project_url(stage.project_id)}


def project_counts():
    by_status = {r["status"]: r["n"] for r in Project.objects.order_by().values("status").annotate(n=Count("id"))}
    return {
        "in_progress": by_status.get(Project.Status.IN_PROGRESS, 0),
        "completed": by_status.get(Project.Status.COMPLETED, 0),
        "suspended": Project.objects.filter(stages__status=ProjectStage.Status.SUSPENDED).distinct().count(),
    }


def unassigned_stages():
    """کار در حال انجام که نه مسئول دارد نه کاندیدا (همان needs_manual_assignment)."""
    return (ProjectStage.objects
            .filter(status=ProjectStage.Status.IN_PROGRESS, assigned_to__isnull=True, **_LIVE)
            .annotate(cand=Count("candidate_users")).filter(cand=0)
            .select_related("project").order_by("started_at"))


def stale_stages(now, skip_ids=()):
    """در حال انجام و بیش از N روز بدون هیچ رویداد (آخرین رویداد، وگرنه زمان شروع)."""
    last_event = StageEvent.objects.filter(stage=OuterRef("pk")).order_by("-created_at").values("created_at")[:1]
    return (ProjectStage.objects
            .filter(status=ProjectStage.Status.IN_PROGRESS, **_LIVE)
            .annotate(last_move=Coalesce(Subquery(last_event), F("started_at")))
            .filter(last_move__lt=now - timedelta(days=STALE_STAGE_DAYS))
            .exclude(pk__in=list(skip_ids))
            .select_related("project", "assigned_to").order_by("last_move"))


def slow_approvals(now):
    return (StageApproval.objects
            .filter(decision=StageApproval.Decision.PENDING, stage__project__status=Project.Status.IN_PROGRESS,
                    sent_at__lt=now - timedelta(days=SLOW_APPROVAL_DAYS))
            .select_related("stage__project", "sent_to_party").order_by("sent_at"))


def overdue_invoices(today):
    """فاکتورِ تاییدشده‌ی مشتری (مرحله‌ی تایید انجام شده) با مانده، که از سررسید (وگرنه صدور) بیش از N روز گذشته.
    پیش‌فاکتورِ تاییدنشده بدهی حساب نمی‌شود."""
    confirmed = Exists(ProjectStage.objects.filter(
        project=OuterRef("project"), step_template__requires_payment_selection=True,
        status=ProjectStage.Status.DONE))
    return (Invoice.objects.exclude(status__in=[Invoice.Status.CANCELLED, Invoice.Status.PAID])
            .annotate(confirmed=confirmed,
                      remaining=ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY),
                      due=Coalesce("due_date", "issue_date"))
            .filter(confirmed=True, remaining__gt=0, due__lt=today - timedelta(days=OVERDUE_INVOICE_DAYS))
            .select_related("billed_party", "project").order_by("due"))


def previous_month_open(today=None):
    """از روز ۵ هر ماه شمسی، اگر ماه قبل هنوز بسته نشده، برچسبش را می‌دهد."""
    today = today or timezone.localdate()
    if jdatetime.date.fromgregorian(date=today).day < 5:
        return None
    year, month = current_ym()
    year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    if PeriodLock.objects.filter(year=year, month=month, is_locked=True).exists():
        return None
    return month_label(year, month)


def attention_items(stats, now=None):
    now = now or timezone.now()
    today = timezone.localdate()
    items = []

    def add(key, label, count, *, level="warning", url=None, hint="", rows=None):
        if count:
            items.append({"key": key, "label": label, "count": count, "level": level,
                          "url": url, "hint": hint, "rows": rows or []})

    unassigned = unassigned_stages()
    unassigned_ids = list(unassigned.values_list("pk", flat=True))
    add("unassigned", "مرحله‌ی بدون مسئول", len(unassigned_ids), level="error",
        hint="کار در حال انجام است ولی کسی مسئول یا کاندیدای آن نیست.",
        rows=[_stage_row(s, now) for s in unassigned[:LIST_LIMIT]])

    suspended = (ProjectStage.objects.filter(status=ProjectStage.Status.SUSPENDED, **_LIVE)
                 .select_related("project").order_by("started_at"))
    add("suspended", "مرحله‌ی معلق", suspended.count(), level="error",
        hint="تصمیم مدیر لازم است: بازگشت به چرخه یا لغو پروژه.",
        rows=[_stage_row(s, now) for s in suspended[:LIST_LIMIT]])

    stale = stale_stages(now, unassigned_ids)
    add("stale", f"بیش از {_fa(STALE_STAGE_DAYS)} روز بدون حرکت", stale.count(),
        hint="مسئول دارد ولی مرحله جلو نرفته است.",
        rows=[_stage_row(s, now, since=s.last_move,
                         extra=(s.assigned_to.get_full_name() or s.assigned_to.username) if s.assigned_to else "")
              for s in stale[:LIST_LIMIT]])

    slow = slow_approvals(now)
    add("slow_approval", f"منتظر پاسخ مشتری بیش از {_fa(SLOW_APPROVAL_DAYS)} روز", slow.count(),
        hint="با مشتری تماس بگیرید.",
        rows=[{"title": f"{a.stage.project.name} — {a.stage.client_label or a.stage.title}",
               "sub": _fa(f"{_since(a.sent_at, now)} روز منتظر پاسخ {a.sent_to_party.name}"),
               "url": _project_url(a.stage.project_id)} for a in slow[:LIST_LIMIT]])

    pending = Payment.objects.filter(status=Payment.Status.PENDING).exclude(method=Payment.Method.GATEWAY)
    oldest = pending.order_by("created_at").values_list("created_at", flat=True).first()
    add("payments", "پرداخت منتظر تایید", pending.count(), url=reverse("finance:payments_review"),
        hint=_fa(f"قدیمی‌ترین: {_since(oldest, now)} روز پیش") if oldest else "")

    overdue = list(overdue_invoices(today))
    add("overdue", f"فاکتور سررسیدگذشته (بیش از {_fa(OVERDUE_INVOICE_DAYS)} روز)", len(overdue), level="error",
        url=reverse("finance:accounting_customers"),
        hint="جمع مانده: " + _fa(separate_digits(sum(i.remaining for i in overdue))) + " تومان",
        rows=[{"title": f"{i.number} — {i.billed_party.name}", "sub": i.project.name,
               "amount": i.remaining, "url": reverse("finance:accounting_project", args=[i.project_id])}
              for i in overdue[:LIST_LIMIT]])

    label = previous_month_open(today)
    if label:
        add("previous_month", f"ماه {label} هنوز بسته نشده", 1, level="info", url=reverse("finance:accounting_periods"),
            hint="بعد از رسیدگی به پرداخت‌های منتظر، ماه را ببندید.")

    add("part_requests", "درخواست قطعه‌ی بی‌پاسخ",
        PartRequest.objects.filter(status=PartRequest.Status.REQUESTED).count(),
        hint="انباردار باید تحویل یا رد کند.")

    integrity = stats["integrity"]
    if integrity["diff"] != 0 or integrity["unclassified_in"] != 0:
        add("integrity", "موجودی انبار با حرکت‌ها هم‌خوان نیست", 1, level="error",
            hint="گزارش دقیق: دستور audit_accounting.")

    add("low_stock", "کالای رو به اتمام", low_stock_items_count(), level="info")

    add("failed_notifications", f"اطلاع‌رسانی ناموفق ({_fa(FAILED_NOTIFICATION_DAYS)} روز اخیر)",
        Notification.objects.filter(status=Notification.Status.FAILED,
                                    created_at__gte=now - timedelta(days=FAILED_NOTIFICATION_DAYS)).count(),
        url=reverse("admin:notifications_notification_changelist") + "?status__exact=failed")

    items.sort(key=lambda i: _LEVEL_RANK[i["level"]])
    return items


def dashboard_context():
    stats = accounting.accounting_overview("this_month")
    return {"counts": project_counts(), "stats": stats, "attention": attention_items(stats)}
