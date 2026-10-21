from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlsplit
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render
from utils.jalali import jalali_str
from utils.jalali_forms import JalaliDateField
from utils.table_export import export_context, export_response

_FA_AR_DIGITS_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

FILTER_TEXT = "text"
FILTER_NUMBER_RANGE = "number_range"
FILTER_SELECT = "select"
FILTER_BOOLEAN = "boolean"
# بازه‌ی تاریخ شمسی: ستون با filter_key و filter_field (فیلد ORM). "allow_future": True = بدون سقف «امروز» (مثل ددلاین)؛
# "date_only": True = فیلد DateField (وگرنه DateTimeField). فقط تاریخ شروع یعنی «تا امروز».
FILTER_DATE_RANGE = "date_range"


def paginate(request, queryset, *, param_prefix="", page_size_default=10, page_size_choices=(10, 20, 50)):
    """
    صفحه‌بندی امن: شماره‌ی صفحه و تعداد سطر از querystring خوانده می‌شوند؛
    هر مقدار نامعتبر بی‌سروصدا به نزدیک‌ترین مقدار معتبر اصلاح می‌شود.
    param_prefix برای این است که چند جدول مستقل در یک صفحه با هم تداخل نکنند.
    """
    page_param = f"{param_prefix}page"
    size_param = f"{param_prefix}page_size"

    try:
        page_size = int(request.GET.get(size_param, page_size_default))
    except (TypeError, ValueError):
        page_size = page_size_default
    if page_size not in page_size_choices:
        page_size = page_size_default

    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get(page_param, 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages or 1)

    return {
        "page_obj": page_obj,
        "paginator": paginator,
        "page_param": page_param,
        "size_param": size_param,
        "page_size": page_size,
        "page_size_choices": page_size_choices,
    }


def _normalize_digits(value):
    """ارقام فارسی/عربی داخل متن را به انگلیسی تبدیل می‌کند تا جستجو/فیلتر روی مقادیری
    که کاربر با کیبورد فارسی تایپ کرده هم کار کند."""
    return (value or "").translate(_FA_AR_DIGITS_TO_EN)


def _parse_decimal_safe(raw):
    """رشته را با ارقام فارسی/جداکننده به Decimal تبدیل می‌کند؛ نامعتبر یا خالی => None
    (نادیده گرفته می‌شود، هرگز خطا نمی‌دهد چون این فیلتر روی URL کاربر نهایی است)."""
    text = _normalize_digits(raw).replace(",", "").replace("٬", "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _parse_jalali_safe(raw):
    """تاریخ شمسی (ارقام فارسی یا لاتین، جداکننده / یا -) ← date میلادی.
    خالی، نامعتبر یا خارج از ۱۹۰۰ تا ۲۹۹۹ ← None؛ هرگز خطا نمی‌دهد (ورودی از URL است)."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        day = JalaliDateField().to_python(raw)
    except ValidationError:
        return None
    return day if day and 1900 <= day.year <= 2999 else None


def _date_q(field, start, end, *, date_only):
    """بازه‌ی بسته‌ی روزانه [start, end]؛ هر کدام None یعنی بدون محدودیت. روز آخر کامل (تا ۲۳:۵۹) حساب می‌شود."""
    q = Q()
    if date_only:
        if start:
            q &= Q(**{f"{field}__gte": start})
        if end:
            q &= Q(**{f"{field}__lte": end})
        return q
    if start:
        q &= Q(**{f"{field}__gte": timezone.make_aware(datetime.combine(start, time.min))})
    if end:
        q &= Q(**{f"{field}__lt": timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min))})
    return q


def _date_summary(from_d, to_d, today=None):
    """متن بازه‌ی اعمال‌شده؛ today فقط وقتی داده می‌شود که پایان خودکار «امروز» است."""
    def show(day):
        return jalali_str(day, fmt="%Y/%m/%d")
    if from_d and to_d:
        return f"فقط روز {show(from_d)}" if from_d == to_d else f"از {show(from_d)} تا {show(to_d)}"
    if from_d:
        return f"از {show(from_d)} تا امروز ({show(today)})" if today else f"از {show(from_d)} به بعد"
    if to_d:
        return f"تا {show(to_d)}"
    return ""


def build_table_context(request, queryset, *, columns, row_builder, container_id,
                          param_prefix="", page_size_default=10, page_size_choices=(10, 20, 50),
                          empty_icon="folder-kanban", empty_text="موردی برای نمایش نیست.",
                          list_url=None, search_fields=None, search_placeholder="جستجو...",
                          export_enabled=True, export_extra=None):
    """
    columns: [{"label": "..."}, ...].
      کلید اختیاری "sort_field": فیلد/annotation واقعی ORM برای سورت (whitelist سمت سرور؛
        پارامتر GET هرگز مستقیم به order_by() داده نمی‌شود).
      کلیدهای اختیاری برای فیلتر پیشرفته‌ی مودال (T2) — همه‌ی این‌ها با هم می‌آیند و فقط وقتی
      "filter_key" و "filter_type" هر دو حاضر باشند آن ستون واقعاً فیلترپذیر می‌شود:
        "filter_key": اسلاگ کوتاه یکتا برای همین ستون در URL.
        "filter_type": یکی از "text" | "number_range" | "select" | "boolean".
        "filter_field": فیلد/lookup واقعی ORM برای فیلتر (پیش‌فرض = filter_key).
        "choices": فقط برای filter_type="select"؛ [(value, label), ...] — همان whitelist مقادیر مجاز.
        "true_label"/"false_label": فقط برای filter_type="boolean"، برچسب گزینه‌ها (پیش‌فرض «بله»/«خیر»).
    search_fields: لیست فیلدهای ORM (lookup چندمرحله‌ای هم مجاز) برای جستجوی icontains با OR.

    row_builder از فیلتر/سورت/جستجو کاملاً بی‌خبر می‌ماند؛ همه روی خودِ queryset، قبل از صفحه‌بندی
    اعمال می‌شوند. خروجی، علاوه بر کلیدهای T1، شامل: columns (نسخه‌ی augmented با مقدار فعلی هر
    فیلتر روی خودش)، has_modal، active_filter_count، reset_url، param_prefix — یعنی هر چیزی که
    تمپلیت برای رندر مودال لازم دارد، بدون این‌که ویو کاری با جزئیات پارامترها داشته باشد.
    """
    search_param = f"{param_prefix}q"
    sort_param = f"{param_prefix}sort"
    dir_param = f"{param_prefix}dir"
    page_param = f"{param_prefix}page"
    size_param = f"{param_prefix}page_size"

    search_query = request.GET.get(search_param, "").strip()
    if search_query and search_fields:
        normalized = _normalize_digits(search_query)
        q_filter = Q()
        for field in search_fields:
            q_filter |= Q(**{f"{field}__icontains": search_query})
            if normalized != search_query:
                q_filter |= Q(**{f"{field}__icontains": normalized})
        queryset = queryset.filter(q_filter).distinct()

    sortable_fields = {col["sort_field"] for col in columns if col.get("sort_field")}
    sort_field = request.GET.get(sort_param, "").strip()
    sort_dir = request.GET.get(dir_param, "asc").strip().lower()
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"
    if sort_field and sort_field in sortable_fields:
        queryset = queryset.order_by(sort_field if sort_dir == "asc" else f"-{sort_field}")
    else:
        sort_field = ""   # چیزی صریحاً انتخاب نشده؛ ترتیب queryset ورودی دست‌نخورده می‌ماند

    # --- فیلتر پیشرفته (مودال، T2) ---
    modal_reset_params = {sort_param, dir_param, page_param}
    active_filter_count = 0
    date_params, date_active = set(), False
    augmented_columns = []

    for col in columns:
        col = dict(col)
        f_key, f_type = col.get("filter_key"), col.get("filter_type")
        if f_key and f_type:
            f_field = col.get("filter_field", f_key)

            if f_type == FILTER_DATE_RANGE:
                from_param, to_param = f"{param_prefix}ffrom_{f_key}", f"{param_prefix}fto_{f_key}"
                modal_reset_params |= {from_param, to_param}
                date_params |= {from_param, to_param}
                from_d = _parse_jalali_safe(request.GET.get(from_param, ""))
                to_d = _parse_jalali_safe(request.GET.get(to_param, ""))
                if from_d and to_d and from_d > to_d:
                    from_d, to_d = to_d, from_d          # ترتیب برعکس: جابه‌جا
                col["filter_value_from"] = jalali_str(from_d, fmt="%Y/%m/%d") if from_d else ""
                col["filter_value_to"] = jalali_str(to_d, fmt="%Y/%m/%d") if to_d else ""
                today = timezone.localdate()
                auto_today = bool(from_d and not to_d and not col.get("allow_future"))   # فقط شروع ← تا امروز
                col["date_summary"] = _date_summary(from_d, to_d, today if auto_today else None)
                # placeholder به‌جای جمله‌ی راهنما: فقط شروع ← «تا» خودکار «امروز» است؛ فقط پایان ← «از» «از ابتدا» است
                col["date_from_hint"] = "از ابتدا" if (to_d and not from_d) else "از تاریخ"
                col["date_to_hint"] = "امروز" if auto_today else "تا تاریخ"
                if from_d or to_d:
                    date_active = True
                    queryset = queryset.filter(_date_q(
                        f_field, from_d, today if auto_today else to_d, date_only=bool(col.get("date_only"))))
            elif f_type == FILTER_NUMBER_RANGE:
                min_param, max_param = f"{param_prefix}fmin_{f_key}", f"{param_prefix}fmax_{f_key}"
                modal_reset_params |= {min_param, max_param}
                min_raw = request.GET.get(min_param, "").strip()
                max_raw = request.GET.get(max_param, "").strip()
                col["filter_value_min"], col["filter_value_max"] = min_raw, max_raw
                min_val, max_val = _parse_decimal_safe(min_raw), _parse_decimal_safe(max_raw)
                if min_val is not None:
                    queryset = queryset.filter(**{f"{f_field}__gte": min_val})
                    active_filter_count += 1
                if max_val is not None:
                    queryset = queryset.filter(**{f"{f_field}__lte": max_val})
                    active_filter_count += 1
            else:
                f_param = f"{param_prefix}f_{f_key}"
                modal_reset_params.add(f_param)
                raw_val = request.GET.get(f_param, "").strip()
                col["filter_value"] = raw_val
                if raw_val:
                    if f_type == FILTER_BOOLEAN and raw_val in ("1", "0"):
                        queryset = queryset.filter(**{f_field: raw_val == "1"})
                        active_filter_count += 1
                    elif f_type == FILTER_SELECT:
                        valid_values = {str(choice_val) for choice_val, _label in col.get("choices", [])}
                        if raw_val in valid_values:
                            queryset = queryset.filter(**{f_field: raw_val})
                            active_filter_count += 1
                    elif f_type == FILTER_TEXT:
                        normalized = _normalize_digits(raw_val)
                        q = Q(**{f"{f_field}__icontains": raw_val})
                        if normalized != raw_val:
                            q |= Q(**{f"{f_field}__icontains": normalized})
                        queryset = queryset.filter(q)
                        active_filter_count += 1
        augmented_columns.append(col)

    reset_params = request.GET.copy()
    for name in modal_reset_params:
        reset_params.pop(name, None)
    base_url = list_url or request.path
    reset_qs = reset_params.urlencode()
    reset_url = f"{base_url}?{reset_qs}" if reset_qs else base_url

    has_modal = any(c.get("sort_field") or (c.get("filter_key") and c.get("filter_type")
                                            and c.get("filter_type") != FILTER_DATE_RANGE) for c in augmented_columns)
    has_date_filter = any(c.get("filter_key") and c.get("filter_type") == FILTER_DATE_RANGE for c in augmented_columns)
    skip_in_date_form = date_params | {page_param}
    date_preserved_params = [(k, v) for k in request.GET if k not in skip_in_date_form for v in request.GET.getlist(k)]
    date_clear = request.GET.copy()
    for name in skip_in_date_form:
        date_clear.pop(name, None)
    date_clear_qs = date_clear.urlencode()
    date_reset_url = f"{base_url}?{date_clear_qs}" if date_clear_qs else base_url

    pg = paginate(request, queryset, param_prefix=param_prefix,
                  page_size_default=page_size_default, page_size_choices=page_size_choices)

    preserved_params = [
        (key, value)
        for key in request.GET
        if key not in (search_param, page_param)
        for value in request.GET.getlist(key)
    ]
    show_pagination = pg["paginator"].num_pages > 1 or pg["paginator"].count > page_size_choices[0]

    rows = [row_builder(obj) for obj in pg["page_obj"].object_list]

    context = dict(pg)
    context.update({
        "columns": augmented_columns,
        "rows": rows,
        "container_id": container_id,
        "empty_icon": empty_icon,
        "empty_text": empty_text,
        "list_url": base_url,
        "search_enabled": bool(search_fields),
        "search_query": search_query,
        "search_param": search_param,
        "search_placeholder": search_placeholder,
        "sort_field": sort_field,
        "sort_dir": sort_dir,
        "sort_param": sort_param,
        "dir_param": dir_param,
        "has_modal": has_modal,
        "active_filter_count": active_filter_count,
        "reset_url": reset_url,
        "param_prefix": param_prefix,
        "preserved_params": preserved_params,
        "show_pagination": show_pagination,
        "has_date_filter": has_date_filter,
        "date_active": date_active,
        "date_preserved_params": date_preserved_params,
        "date_reset_url": date_reset_url,
    })
    # اکسپورت CSV: فقط با قابلیت tables.export؛ export_extra = ستون‌های اضافه‌ی [{"label", "value": fn(obj)}]
    # ستونی که "no_export": True دارد (مثل «عملیات») در چک‌لیست نمی‌آید.
    context.update(export_context(
        request, queryset=queryset, columns=augmented_columns, row_builder=row_builder,
        extras=export_extra, enabled=export_enabled, container_id=container_id,
        param_prefix=param_prefix, page_param=page_param, total=pg["paginator"].count))
    return context


def render_table(request, context, template="utils/partials/generic_table.html"):
    """
    رندر اندپوینت‌های تکه‌ای جدول + تنظیم HX-Replace-Url روی «آدرس صفحه‌ی میزبان»
    (نه آدرس خودِ اندپوینت). آدرس فعلی مرورگر از هدر HX-Current-URL می‌آید؛ پارامترهای
    همین جدول (همه‌ی کلیدهای با param_prefix) با مقدار جدید جایگزین می‌شوند و بقیه
    (جدول‌های دیگر و تب فعال) دست‌نخورده می‌مانند. param_prefix باید غیرخالی باشد.
    """
    if request.GET.get(context.get("export_param", ""), "") == "csv" and request.path == context.get("list_url"):
        return export_response(request, context)
    response = render(request, template, context)
    current_url = request.headers.get("HX-Current-URL")
    if not (request.headers.get("HX-Request") and current_url):
        return response

    prefix = context["param_prefix"]
    parts = urlsplit(current_url)
    current_pairs = parse_qsl(parts.query, keep_blank_values=True)

    def is_own(key):
        return bool(prefix) and key.startswith(prefix)

    pairs = [(k, v) for k, v in current_pairs if k != "tab" and not is_own(k)]
    pairs += [(k, request.GET.getlist(k)[-1]) for k in request.GET if is_own(k)]
    tab = request.GET.get("tab") or dict(current_pairs).get("tab")
    if tab:
        pairs.append(("tab", tab))
    response["HX-Replace-Url"] = parts.path + ("?" + urlencode(pairs) if pairs else "")
    return response
