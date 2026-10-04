from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404
from django.shortcuts import redirect, render

from utils.jalali import to_fa_digits

from . import bulk
from .services import user_can_manage_inventory

PAGES = {
    "opening": {
        "title": "ورود گروهی موجودی اولیه",
        "sub": "ثبت موجودی اولیه‌ی چند صد کالا یک‌جا، با پیش‌نمایش و بدون خطر نیمه‌کاره‌ماندن.",
        "steps": "فهرست کالاها را دانلود کنید، ستون «مقدار» و «بهای واحد (تومان)» را در Excel پر کنید، سه ستون اول را کپی کنید و در کادر زیر paste کنید. نام کالا باید با فهرست یکی باشد.",
        "button": "ثبت موجودی اولیه",
    },
    "count": {
        "title": "انبارگردانی",
        "sub": "شمارش انبار را وارد کنید؛ فقط اختلاف با موجودی سیستم ثبت می‌شود.",
        "steps": "فهرست را دانلود کنید، ستون «مقدار شمارش‌شده» را پر کنید (کالای شمارش‌نشده را خالی بگذارید)، دو ستون اول را کپی کنید و در کادر زیر paste کنید.",
        "button": "ثبت انبارگردانی",
    },
}


def _page(request, mode):
    pasted = request.POST.get("pasted", "")
    notes = (request.POST.get("notes") or "").strip()
    preview, digest = None, ""
    if request.method == "POST":
        try:
            preview = bulk.build_preview(mode, pasted)
            digest = bulk.content_digest(mode, pasted, notes)
            if request.POST.get("action") == "confirm":
                if request.POST.get("digest") != digest:
                    raise ValueError("متن بعد از پیش‌نمایش تغییر کرده؛ دوباره پیش‌نمایش بگیرید.")
                count = bulk.commit(mode, pasted, notes, request.user,
                                    acknowledged=request.POST.get("ack") == "1")
                messages.success(request, f"{to_fa_digits(count)} ردیف ثبت شد.")
                return redirect("home")
        except ValueError as e:
            messages.error(request, str(e))
    return render(request, "inventory/bulk_entry.html", {
        **PAGES[mode], "mode": mode, "pasted": pasted, "notes": notes, "preview": preview, "digest": digest,
    })


@login_required
@user_passes_test(user_can_manage_inventory)
def bulk_opening_page(request):
    return _page(request, "opening")


@login_required
@user_passes_test(user_can_manage_inventory)
def bulk_reconciliation_page(request):
    return _page(request, "count")


@login_required
@user_passes_test(user_can_manage_inventory)
def bulk_template(request, mode):
    if mode not in bulk.MODES:
        raise Http404
    return bulk.template_response(mode)
