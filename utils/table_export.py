import csv
import re
from datetime import date, datetime
from decimal import Decimal

from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import content_disposition_header

from core.capabilities import can
from utils.jalali import jalali_str, to_fa_digits
from utils.utils import separate_digits

MAX_EXPORT_ROWS = 5000
MAX_PDF_ROWS = 500   # PDF همان لحظه ساخته می‌شود؛ بیشتر از این کند و سنگین است

_TO_LATIN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_EMPTY = {"", "—", "-", "None"}
_MONEY = re.compile(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$")
_PLAIN = re.compile(r"^-?(0|[1-9]\d{0,10})(\.\d+)?$")
_DATE = re.compile(r"^\d{4}/\d{2}/\d{2}( \d{2}:\d{2})?$")
_DIGITS = re.compile(r"^\d+$")
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def export_value(value):
    """مقدار یک خانه ← متن CSV.
    عدد = لاتین و بدون ویرگول (Excel جمع می‌زند)؛ تاریخ = لاتین؛ جای‌نگهدار «—» = خالی؛
    رشته‌ی تماماً رقمیِ دارای صفر اول یا بلندتر از ۱۱ رقم (تلفن، کد، شناسه‌ی صیادی) = ارقام فارسی تا Excel صفر اول و دقت را نخورد؛
    متنی که با = + - @ شروع شود با ' شروع می‌شود (جلوی اجرای فرمول)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "بله" if value else "خیر"
    if isinstance(value, datetime):
        return jalali_str(value, fmt="%Y/%m/%d %H:%M", persian=False)
    if isinstance(value, date):
        return jalali_str(value, fmt="%Y/%m/%d", persian=False)
    if isinstance(value, (int, float, Decimal)):
        return format(Decimal(str(value)).normalize(), "f")
    text = str(value).strip()
    if text in _EMPTY:
        return ""
    latin = text.translate(_TO_LATIN).replace("٬", ",").replace("٫", ".")
    if _MONEY.match(latin):
        return latin.replace(",", "")
    if _PLAIN.match(latin) or _DATE.match(latin):
        return latin
    if _DIGITS.match(latin):
        return to_fa_digits(latin)
    if text.startswith(_DANGEROUS):
        return "'" + text
    return text


def available_columns(columns, extras):
    """چک‌لیست مودال: ستون‌های جدول (بدون no_export) + ستون‌های اضافه. کلید c<i> و x<i>."""
    out = [{"key": f"c{i}", "label": col["label"], "extra": False}
           for i, col in enumerate(columns) if not col.get("no_export")]
    out += [{"key": f"x{i}", "label": x["label"], "extra": True} for i, x in enumerate(extras or [])]
    return out


def parse_limit(raw, cap=MAX_EXPORT_ROWS):
    text = str(raw or "").strip().translate(_TO_LATIN)
    if not text.isdigit() or int(text) < 1:
        return cap
    return min(int(text), cap)


def export_context(request, *, queryset, columns, row_builder, extras, enabled, container_id,
                   param_prefix, page_param, total):
    """کلیدهای اکسپورت برای context جدول. بدون قابلیت tables.export یا با enabled=False همه چیز خاموش است."""
    user = getattr(request, "user", None)
    on = bool(enabled and can(user, "tables.export"))
    export_param, cols_param, limit_param = (f"{param_prefix}{k}" for k in ("export", "cols", "limit"))
    ctx = {"export_enabled": on, "export_param": export_param, "cols_param": cols_param, "limit_param": limit_param}
    if not on:
        return ctx
    own = {export_param, cols_param, limit_param, page_param}
    ctx.update({
        "export_columns": available_columns(columns, extras),
        "export_state": [(k, v) for k in request.GET if param_prefix and k.startswith(param_prefix) and k not in own
                         for v in request.GET.getlist(k)],
        "export_total": total,
        "export_max": MAX_EXPORT_ROWS,
        "export_pdf_max": MAX_PDF_ROWS,
        "export_default_limit": min(total, MAX_EXPORT_ROWS) or "",
        "export_source": {"queryset": queryset, "row_builder": row_builder, "columns": columns,
                          "extras": list(extras or [])},
    })
    return ctx


def display_value(value):
    """مقدار یک خانه ← متن خوانا برای PDF (ارقام فارسی، هزارگان، تاریخ شمسی)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "بله" if value else "خیر"
    if isinstance(value, datetime):
        return jalali_str(value, fmt="%Y/%m/%d %H:%M")
    if isinstance(value, date):
        return jalali_str(value, fmt="%Y/%m/%d")
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        if number == number.to_integral_value():
            return to_fa_digits(separate_digits(number))
        return to_fa_digits(format(number.normalize(), "f"))
    text = str(value).strip()
    return text or "—"


def _selected(request, context, cap):
    """ستون‌های انتخاب‌شده، آبجکت‌ها و مقدار خام هر خانه (مشترک بین CSV و PDF)."""
    source = context["export_source"]
    available = available_columns(source["columns"], source["extras"])
    chosen = set(request.GET.getlist(context["cols_param"]))
    picked = [c for c in available if c["key"] in chosen] or available
    limit = parse_limit(request.GET.get(context["limit_param"]), cap)

    objects = list(source["queryset"][:limit])
    base = [int(c["key"][1:]) for c in picked if not c["extra"]]
    extra = [int(c["key"][1:]) for c in picked if c["extra"]]
    extras = source["extras"]

    rows = []
    for obj in objects:
        cells = source["row_builder"](obj)["cells"] if base else []
        row = []
        for i in base:
            cell = cells[i] if i < len(cells) else {}
            row.append(None if cell.get("type") == "actions" else cell.get("value"))
        row += [extras[i]["value"](obj) for i in extra]
        rows.append(row)
    return picked, objects, rows


def _csv_response(picked, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response.write("\ufeff")   # BOM: Excel فارسی را درست بخواند
    writer = csv.writer(response)
    writer.writerow([c["label"] for c in picked])
    for row in rows:
        writer.writerow([export_value(v) for v in row])
    return response


def _pdf_response(request, picked, rows, total):
    import weasyprint
    html = render_to_string("utils/table_pdf.html", {
        "title": "خروجی جدول",
        "stamp": jalali_str(timezone.now(), fmt="%Y/%m/%d %H:%M"),
        "count": to_fa_digits(len(rows)),
        "total": to_fa_digits(total),
        "truncated": total > len(rows),
        "headers": [c["label"] for c in picked],
        "rows": [[display_value(v) for v in row] for row in rows],
    })
    pdf = weasyprint.HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    return HttpResponse(pdf, content_type="application/pdf")


def export_response(request, context):
    """فایل CSV یا PDF همان جدول با جستجو، فیلتر و ترتیب فعلی؛ همه‌ی صفحه‌ها تا سقف limit.
    PDF همان لحظه ساخته می‌شود و جایی ذخیره نمی‌شود."""
    if not context.get("export_enabled"):
        raise Http404
    is_pdf = request.GET.get(context["export_param"]) == "pdf"
    picked, objects, rows = _selected(request, context, MAX_PDF_ROWS if is_pdf else MAX_EXPORT_ROWS)

    from finance.accounting import log_event
    from finance.models import AccountingEvent
    state = "&".join(f"{k}={v}" for k, v in context["export_state"])[:120]
    kind = "PDF" if is_pdf else "CSV"
    log_event(kind=AccountingEvent.Kind.EXPORT, actor=request.user,
              text=(f"خروجی {kind} از جدول {context['container_id']}: {to_fa_digits(len(objects))} ردیف، "
                    f"ستون‌ها: {'، '.join(c['label'] for c in picked)}"
                    + (f" — فیلتر: {state}" if state else "")))

    response = _pdf_response(request, picked, rows, context["export_total"]) if is_pdf else _csv_response(picked, rows)
    stamp = jalali_str(timezone.localdate(), fmt="%Y-%m-%d", persian=False)
    response["Content-Disposition"] = content_disposition_header(
        True, f"{context['container_id']}-{stamp}.{'pdf' if is_pdf else 'csv'}")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
