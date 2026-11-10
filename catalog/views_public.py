from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from . import showcase

LIST_TEXT = {
    "service": ("خدمات ما", "خدماتی که انجام می‌دهیم. برای سفارش و قیمت با دفتر تماس بگیرید."),
    "item": ("محصولات ما", "محصولاتی که عرضه می‌کنیم. برای خرید با دفتر تماس بگیرید."),
}


def _page_number(request):
    raw = request.GET.get("page", "1")
    return min(int(raw), 1000) if raw.isdigit() and int(raw) >= 1 else 1


def _list(request, kind):
    cards, more = showcase.list_page(kind, showcase.scope_for(request.user), 1)
    title, sub = LIST_TEXT[kind]
    return render(request, "catalog/list.html", {
        "title": title, "sub": sub, "cards": cards, "more": more, "page": 1, "next_page": 2,
        "more_url": reverse(f"catalog:{kind}_list_more")})


def _more(request, kind):
    page = _page_number(request)
    cards, more = showcase.list_page(kind, showcase.scope_for(request.user), page)
    return render(request, "catalog/partials/grid_page.html", {
        "cards": cards, "more": more, "page": page, "next_page": page + 1, "more_url": request.path})


def _detail(request, kind, pk):
    scope = showcase.scope_for(request.user)
    obj = showcase.get_visible(kind, pk, scope)
    if obj is None:
        raise Http404
    return render(request, "catalog/detail.html", {
        "kind": kind, "obj": obj, "content": showcase.detail(kind, obj),
        "related": showcase.related(kind, obj, scope),
        "related_title": "خدمات دیگر" if kind == "service" else "محصولات مشابه",
        "can_edit": scope == "all"})


@login_required
def service_list(request):
    return _list(request, "service")


@login_required
def item_list(request):
    return _list(request, "item")


@login_required
def service_list_more(request):
    return _more(request, "service")


@login_required
def item_list_more(request):
    return _more(request, "item")


@login_required
def service_detail(request, pk):
    return _detail(request, "service", pk)


@login_required
def item_detail(request, pk):
    return _detail(request, "item", pk)
