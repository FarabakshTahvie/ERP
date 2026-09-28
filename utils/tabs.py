"""
موتور تب‌های چندگانه با حفظ وضعیت روی رفرش کامل صفحه (URL-driven active tab).

هدف: خودِ ویو نباید بفهمد «پارامتر تب کدام است» یا «کدام تب پیش‌فرض است» — این‌ها
یک‌بار اینجا حل می‌شوند. ویو فقط فهرست تب‌ها (کلید، برچسب، شمارش سبک اختیاری،
رندر سنگین اختیاری) را می‌دهد.
"""

TAB_PARAM = "tab"


def resolve_active_tab(request, tab_keys, default_key=None):
    """
    کلید تب فعال را از querystring می‌خواند (پارامتر ثابت 'tab')؛ اگر پارامتر نبود،
    نامعتبر بود، یا اصلاً در tab_keys نبود، به default_key (یا اولین کلید) برمی‌گردد.
    این تنها جایی است که این تصمیم گرفته می‌شود.
    """
    requested = request.GET.get(TAB_PARAM, "").strip()
    if requested in tab_keys:
        return requested
    if default_key in tab_keys:
        return default_key
    return tab_keys[0] if tab_keys else None


def build_tabs_context(request, tabs):
    """
    tabs: لیستی از دیکشنری‌ها به شکل:
        {
            "key": "my_tasks",                # یکتا در همین صفحه
            "label": "کارهای من",
            "url": "...",                      # آدرس htmx برای لود این تب با کلیک
            "container_id": "tab-panel-x",     # id ای که htmx باید به آن سوآپ کند
            "count_builder": callable,         # اختیاری: callable() -> int؛ برای *همه‌ی* تب‌ها صدا زده می‌شود
            "eager_render": callable,          # اختیاری: callable() -> str HTML؛ *فقط* اگر تب فعال باشد صدا زده می‌شود
            "hint": "...",                     # اختیاری: یک خط توضیح بالای پنل (با CSS سوآپ نمی‌شود)
        }
    خروجی برای پاس‌دادن مستقیم به تمپلیت:
        {"tabs": [...augmented...], "active_tab_key": "...", "tab_param": "tab"}
    """
    tab_keys = [t["key"] for t in tabs]
    default_key = tabs[0]["key"] if tabs else None
    active_key = resolve_active_tab(request, tab_keys, default_key=default_key)

    augmented = []
    for t in tabs:
        t = dict(t)
        is_active = t["key"] == active_key
        t["is_active"] = is_active
        t.setdefault("count", None)
        if t.get("count_builder") is not None:
            t["count"] = t["count_builder"]()
        t["eager_html"] = t["eager_render"]() if (is_active and t.get("eager_render")) else None
        augmented.append(t)

    return {
        "tabs": augmented,
        "active_tab_key": active_key,
        "tab_param": TAB_PARAM,
    }
