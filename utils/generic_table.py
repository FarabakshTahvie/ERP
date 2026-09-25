from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def paginate(request, queryset, *, param_prefix="", page_size_default=10, page_size_choices=(10, 20, 50)):
    """
    صفحه‌بندی امن: شماره‌ی صفحه و تعداد سطر از querystring خوانده می‌شوند؛
    هر مقدار نامعتبر بی‌سروصدا به نزدیک‌ترین مقدار معتبر اصلاح می‌شود.
    param_prefix برای این است که چند جدول مستقل در یک صفحه با هم تداخل نکنند
    (مثلاً 'mytasks_' و 'claimable_').
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


def build_table_context(request, queryset, *, columns, row_builder, container_id,
                          param_prefix="", page_size_default=10, page_size_choices=(10, 20, 50),
                          empty_icon="folder-kanban", empty_text="موردی برای نمایش نیست.",
                          list_url=None):
    """
    columns: [{"label": "..."}, ...] فقط برای سرستون‌ها.
    row_builder: تابعی که یک آبجکت می‌گیرد و برمی‌گرداند:
        {"url": "...یا None", "cells": [{"type": "text"|"badge"|"link"|"muted"|"actions", ...}, ...]}
    container_id: آی‌دی یکتای این ناحیه‌ی جدول (برای hx-target از بیرون و hx-get داخلی).
    """
    pg = paginate(request, queryset, param_prefix=param_prefix,
                  page_size_default=page_size_default, page_size_choices=page_size_choices)
    rows = [row_builder(obj) for obj in pg["page_obj"].object_list]
    context = dict(pg)
    context.update({
        "columns": columns,
        "rows": rows,
        "container_id": container_id,
        "empty_icon": empty_icon,
        "empty_text": empty_text,
        "list_url": list_url or request.path,
    })
    return context
