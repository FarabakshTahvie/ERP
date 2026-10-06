from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.models import User
from core.capabilities import can, cap_required
from core.models import Party, Specialty
from finance.aging import debt_invoices, get_customer_aging_data
from finance.models import Invoice, Payment
from projects.models import Project
from utils.generic_table import build_table_context, render_table
from utils.jalali import to_fa_digits
from utils.utils import separate_digits

from . import services

MONEY = DecimalField(max_digits=24, decimal_places=2)


# ---------- کارکنان ----------
def staff_ctx(request):
    show_presence = can(request.user, "activity.view")
    qs = (User.objects.filter(role__in=[User.Role.ADMIN, User.Role.EMPLOYEE])
          .select_related("presence").prefetch_related("specialties")
          .order_by("-is_active", "last_name", "first_name", "username"))

    def row_builder(u):
        cells = [
            {"type": "text", "value": u.get_full_name() or u.username},
            {"type": "muted", "value": u.get_role_display()},
            {"type": "muted", "value": "، ".join(s.name for s in u.specialties.all()) or "—"},
            {"type": "badge", "value": "فعال" if u.is_active else "غیرفعال",
             "variant": "success" if u.is_active else "neutral"},
        ]
        if show_presence:
            p = getattr(u, "presence", None)
            cells.append({"type": "muted", "value": services.seen_text(p)})
            cells.append({"type": "muted", "value": services.page_label(p.view_name) if p else "—"})
        return {"url": reverse("people:user_detail", args=[u.id]), "cells": cells}

    columns = [
        {"label": "نام", "sort_field": "last_name"},
        {"label": "نقش", "sort_field": "role", "filter_key": "role", "filter_type": "select",
         "choices": [(User.Role.ADMIN.value, "مدیر"), (User.Role.EMPLOYEE.value, "تکنسین")]},
        {"label": "تخصص‌ها"},
        {"label": "وضعیت", "sort_field": "is_active", "filter_key": "active", "filter_type": "boolean",
         "filter_field": "is_active", "true_label": "فعال", "false_label": "غیرفعال"},
    ]
    if show_presence:
        columns += [{"label": "آخرین دیده‌شدن", "sort_field": "presence__last_seen"}, {"label": "آخرین صفحه"}]

    return build_table_context(
        request, qs, columns=columns, row_builder=row_builder,
        container_id="table-people-staff", param_prefix="pe_",
        empty_icon="users", empty_text="کاربری ثبت نشده.",
        list_url=reverse("people:staff_table"),
        search_fields=["first_name", "last_name", "username", "phone_number"],
        search_placeholder="جستجو در نام یا شماره...",
    )


# ---------- مشتریان و شرکا ----------
def _roles_text(p):
    names = [label for flag, label in ((p.is_client, "کارفرما"), (p.is_partner, "شریک تجاری"),
                                       (p.is_contractor, "پیمانکار")) if flag]
    return "، ".join(names) or "—"


def customers_ctx(request):
    rem = ExpressionWrapper(F("total_amount") - F("paid_amount"), output_field=MONEY)
    per_party = (debt_invoices(Invoice.objects.filter(billed_party=OuterRef("pk")))
                 .order_by().values("billed_party"))
    qs = (Party.objects.filter(is_internal=False).filter(Q(is_client=True) | Q(is_partner=True))
          .annotate(
              n_inv=Coalesce(Subquery(per_party.annotate(n=Count("id")).values("n")), Value(0)),
              outstanding=Coalesce(Subquery(per_party.annotate(t=Sum(rem)).values("t"), output_field=MONEY),
                                   Value(Decimal("0")), output_field=MONEY))
          .order_by("name"))

    def row_builder(p):
        return {"url": reverse("people:party_detail", args=[p.id]), "cells": [
            {"type": "text", "value": p.name},
            {"type": "muted", "value": to_fa_digits(p.phone_number) or "—"},
            {"type": "muted", "value": _roles_text(p)},
            {"type": "muted", "value": to_fa_digits(p.n_inv)},
            {"type": "text", "value": to_fa_digits(separate_digits(p.outstanding))},
        ]}

    return build_table_context(
        request, qs,
        columns=[
            {"label": "نام", "sort_field": "name"},
            {"label": "تلفن"},
            {"label": "نقش"},
            {"label": "تعداد فاکتور", "sort_field": "n_inv"},
            {"label": "مانده‌ی فاکتورها (تومان)", "sort_field": "outstanding",
             "filter_key": "outstanding", "filter_type": "number_range"},
        ],
        row_builder=row_builder, container_id="table-people-customers", param_prefix="pc_",
        empty_icon="users", empty_text="طرف‌حسابی ثبت نشده.",
        list_url=reverse("people:customers_table"),
        search_fields=["name", "phone_number", "brand_name"],
        search_placeholder="جستجو در نام یا شماره...",
    )


def _table_page(request, builder, *, nav, title, sub):
    ctx = builder(request)
    ctx.update(nav_active=nav, page_title=title, page_sub=sub)
    return render(request, "people/table_page.html", ctx)


@cap_required("people.view")
def staff_page(request):
    return _table_page(request, staff_ctx, nav="staff", title="کارکنان",
                       sub="مدیران و تکنسین‌ها. برای دیدن پروفایل روی هر ردیف بزنید.")


@cap_required("people.view")
def staff_table(request):
    return render_table(request, staff_ctx(request))


@cap_required("people.view")
def customers_page(request):
    return _table_page(request, customers_ctx, nav="customers", title="مشتریان و شرکا",
                       sub="مانده، مجموع فاکتورهای صادرشده‌ی لغونشده منهای دریافتی واقعی است؛ همان عددِ «مرکز مشتریان».")


@cap_required("people.view")
def customers_table(request):
    return render_table(request, customers_ctx(request))


# ---------- پروفایل‌ها ----------
@cap_required("people.view")
def user_detail(request, user_id):
    person = get_object_or_404(User.objects.select_related("party").prefetch_related("specialties"), pk=user_id)
    show_activity = can(request.user, "activity.view")
    ctx = {"person": person, "can_edit": can(request.user, "people.edit"), "show_activity": show_activity}
    ctx.update(services.user_work_summary(person))
    if show_activity:
        try:
            days = int(request.GET.get("days", 30))
        except ValueError:
            days = 30
        days = days if days in services.FEED_DAYS else 30
        presence = getattr(person, "presence", None)
        ctx.update(feed=services.activity_feed(person, days=days), days=days, days_choices=services.FEED_DAYS,
                   presence=presence, seen=services.seen_text(presence),
                   page=services.page_label(presence.view_name) if presence else "—",
                   history=services.account_history(person))
    return render(request, "people/user_detail.html", ctx)


@cap_required("people.view")
def party_detail(request, party_id):
    party = get_object_or_404(Party, pk=party_id, is_internal=False)
    summary, aging_rows = get_customer_aging_data(party)
    return render(request, "people/party_detail.html", {
        "party": party, "summary": summary, "aging_rows": aging_rows,
        "can_edit": can(request.user, "people.edit"),
        "accounts": party.users.all(),
        "projects": Project.objects.filter(Q(owner=party) | Q(partner=party)).order_by("-created_at")[:30],
        "payments": Payment.objects.filter(invoice__billed_party=party).select_related("invoice").order_by("-created_at")[:30],
        "roles": _roles_text(party),
    })


# ---------- ویرایش (فقط مدیر) ----------
@cap_required("people.edit")
def user_edit(request, user_id):
    person = get_object_or_404(User, pk=user_id)
    selected = {s.id for s in person.specialties.all()}
    values = {"first_name": person.first_name, "last_name": person.last_name,
              "phone_number": person.phone_number or "", "email": person.email,
              "national_code": person.national_code or ""}
    if request.method == "POST":
        values = {k: request.POST.get(k, "") for k in values}
        selected = {int(x) for x in request.POST.getlist("specialties") if x.isdigit()}
        try:
            services.update_user_profile(
                user=person, actor=request.user, specialty_ids=request.POST.getlist("specialties")
                if person.role == User.Role.EMPLOYEE else None, **values)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "اطلاعات ذخیره شد.")
            return redirect("people:user_detail", person.id)
    return render(request, "people/user_edit.html", {
        "person": person, "values": values, "selected": selected,
        "specialties": Specialty.objects.filter(is_active=True).order_by("name"),
    })


@cap_required("people.edit")
@require_POST
@never_cache
def user_reset_password(request, user_id):
    person = get_object_or_404(User, pk=user_id)
    try:
        raw = services.reset_user_password(user=person, actor=request.user)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("people:user_detail", person.id)
    return render(request, "people/password_reset_done.html", {"person": person, "raw_password": raw})


@cap_required("people.edit")
@require_POST
def user_toggle_active(request, user_id):
    person = get_object_or_404(User, pk=user_id)
    target = not person.is_active
    try:
        open_stages = services.set_user_active(user=person, active=target, actor=request.user,
                                               reason=request.POST.get("reason"))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "حساب فعال شد." if target else "حساب غیرفعال شد.")
        if open_stages:
            messages.warning(request, f"{to_fa_digits(open_stages)} مرحله‌ی او به چرخه برگشت (استخر هم‌تخصص‌ها). مرحله‌ی بی‌مسئول در داشبورد دیده می‌شود.")
    return redirect("people:user_detail", person.id)


@cap_required("people.edit")
def party_edit(request, party_id):
    party = get_object_or_404(Party, pk=party_id, is_internal=False)
    values = {"name": party.name, "brand_name": party.brand_name, "phone_number": party.phone_number,
              "secondary_phone": party.secondary_phone, "email": party.email,
              "description": party.description, "credit_limit_raw": str(int(party.credit_limit or 0))}
    if request.method == "POST":
        values = {k: request.POST.get(k, "") for k in values}
        try:
            services.update_party_profile(party=party, actor=request.user, **values)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "اطلاعات ذخیره شد.")
            return redirect("people:party_detail", party.id)
    return render(request, "people/party_edit.html", {"party": party, "values": values})


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from utils.generic_table import _normalize_digits

SEARCH_KINDS = {"parties": "accounting.access", "audience": "broadcast.use"}
_AR, _FA = str.maketrans("يك", "یک"), str.maketrans("یک", "يك")


def _variants(q):
    q = _normalize_digits(q.strip())
    return {q, q.translate(_AR), q.translate(_FA)}


@login_required
def people_search(request):
    kind = request.GET.get("kind", "")
    if kind not in SEARCH_KINDS or not can(request.user, SEARCH_KINDS[kind]):
        raise Http404
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    cond = Q()
    if kind == "parties":
        for v in _variants(q):
            cond |= Q(name__icontains=v) | Q(brand_name__icontains=v) | Q(phone_number__icontains=v)
        qs = (Party.objects.filter(is_internal=False, invoices__isnull=False).filter(cond)
              .distinct().order_by("name")[:10])
        data = [{"id": p.id, "name": p.name, "sub": p.phone_number or ""} for p in qs]
    else:
        for v in _variants(q):
            cond |= (Q(first_name__icontains=v) | Q(last_name__icontains=v)
                     | Q(username__icontains=v) | Q(phone_number__icontains=v))
        qs = User.objects.filter(is_active=True).filter(cond).order_by("last_name", "first_name")[:10]
        data = [{"id": u.id, "name": u.get_full_name() or u.username,
                 "sub": f"{u.get_role_display()} · {u.phone_number or 'بدون شماره'}"} for u in qs]
    return JsonResponse({"results": data})
