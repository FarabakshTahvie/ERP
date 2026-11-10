# بریف ۱: صفحه‌ی «موقعیت‌ها» (شاخه‌ی `feat/saved-locations`)

### قواعد ثابت نشست

```
- شاخه: (هر بریف شاخه‌ی خودش؛ مثلاً feat/<نام>، از main تازه). push و merge به main ممنوع.
- git stash و git reset --hard ممنوع.
- پایتون ۳.۱۲ (لوکال، سرور و CI)؛ سینتکس مخصوص ۳.۱۳ به بعد ممنوع.
- هیچ رمز یا کلیدی در فایل، لاگ یا گزارش ننویس.
- تعداد کل تست‌ها کم نشود (مگر حذف/بازنویسی که خود بریف می‌گوید؛ آن را در گزارش با نام بیاور). نام کلاس یا متد تست تکراری ممنوع.
- فقط کار همین گام. کد بریف را عیناً بگذار، «بهتر» نکن. هر جا کد واقعی با بریف نخواند، توقف و گزارش.
- فقط فایل‌هایی که بریف نام برده دست بخورد.
- تصمیم دسترسی فقط با core/capabilities.py. select_for_update همراه select_related فقط با of=("self",).
- در متن UI این کلمه‌ها ممنوع: «اختیاری»، «فعلاً»، «FIFO»، «اسنپ‌شات»، «اتمیک».
- گزارش: تعداد تست قبل و بعد، نام تست‌های جدید/حذف/بازنویسی‌شده، خروجی makemigrations --check --dry-run، نتیجه‌ی هر mutation با نام تست شکست‌خورده (و برگرداندنش)، فهرست فایل‌ها، انحراف‌ها، git log و git branch -a. گزارش جایگزین تست دستی نیست.
- هیچ متنِ آمده از سرور/کاربر با innerHTML، outerHTML، insertAdjacentHTML، document.write یا eval وارد صفحه نشود؛ حتی در کامنت این کلمه‌ها را ننویس. فقط createElement و textContent.
- در تمپلیت فقط کلاس‌های Tailwind v4 و daisyUI v5. کلاس ممنوع: *-bordered، form-control، label-text، rounded-btn، shadow-sm، badge خالی، btn-warning. بج فقط fb-badge. btn-error فقط با btn-soft.
- در تمپلیت `{{ a.b|default:a.c }}` وقتی a ممکن است None باشد ممنوع (آرگومان فیلتر خطا می‌دهد)؛ از {% if a %}...{% else %}—{% endif %} یا فیلتر |person_name استفاده کن.
- کادر عددی تازه: data-money (مبلغ) یا data-decimal (مقدار اعشاری) یا data-digits (کد رقمی)؛ type="number" ممنوع.
- روی عنصری که با JS مخفی/ظاهر می‌شود، کلاس‌های display مثل flex/grid ننویس (فقط hidden)؛ داخلش یک div با flex بگذار.
- فایل JS تازه باید در static/src/input.css با @source ثبت شود و pnpm run build بدون خطا اجرا شود.
- آیکون فقط از sprite.svg؛ آیکون ناموجود را از خودت نساز.
- ممنوع: ساختن کاربر، تکنسین یا هر رکوردی در دیتابیس واقعی (لوکال یا سرور) برای آزمایش. بررسی خودکار فقط با تست‌های Django.
- seed_test_team فقط اگر کاربر صریحاً خواست. هیچ کاربری پاک نشود.
- تست موجود را فقط با «بازنویسی» اصلاح کن، نه حذفِ بی‌دلیل. هر جا بریف sed یا حذف فایل می‌گوید، بعدش grep بزن و خروجی را در گزارش بیاور.
- اگر یک تست قدیمی به‌خاطر همین بریف شکست و در بریف نامش نیامده، تصمیم نگیر: نامش و علت را گزارش کن و فقط اگر علت مستقیم همین تغییر بود با بازنویسی درستش کن.
```

**کد بریف عیناً گذاشته شود و هر جا با کد واقعی نخواند، توقف و گزارش.**

> بعد از بریف ۱ و ۲ هیچ تست تازه‌ای ننوشته‌ایم؛ همه‌ی تست‌ها در بریف ۳ آمده‌اند. تنها استثنا یک ردیف در ماتریس قابلیت‌هاست (در همین بریف)، چون بدون آن `test_every_capability_is_in_the_matrix` قرمز می‌شود و CI جلوی deploy را می‌گیرد.

### توضیح ساده
مدیر و حسابدار از منوی آواتار، کنار «کارت‌های بانکی»، به صفحه‌ی «موقعیت‌ها» می‌روند. هر موقعیت یک نقطه‌ی دلخواه است (انبار، دفتر، محل قرار) و جدا از `core.Location` پروژه‌هاست، پس مدل تازه‌ای می‌سازیم. از لیست می‌شود موقعیت را اضافه، ویرایش و حذف کرد.

- **انتخاب نقطه:** موقعیت از روی نقشه‌ی نشان، دکمه‌ی «موقعیت من» یا نوشتن دستی مختصات می‌آید.
- **تایید نقطه:** کلیک روی نقشه موقعیت ثبت‌شده را عوض نمی‌کند. فقط یک «نقطه‌ی پیشنهادی» (با رنگ دیگر) می‌گذارد و تا «تایید این نقطه» نخورد چیزی عوض نمی‌شود. تا وقتی نقطه‌ی پیشنهادی تایید یا لغو نشده، ثبت فرم بسته است.
- **لینک‌ها:** هر موقعیت دو لینک قابل کپی دارد. یکی لینک مستقیم نشان (`nshn.ir/?lat=..&lng=..`) و دیگری لینک عمومی `/loc/<کد>/` که بدون ورود باز می‌شود و عنوان، توضیحات، تصویر و دکمه‌های «مشاهده روی نقشه» و «مسیریابی با ماشین» را نشان می‌دهد.

### فایل‌ها
- **تازه:** `locations/` (`__init__.py`، `apps.py`، `models.py`، `services.py`، `views.py`، `urls.py`، مایگریشن)، `templates/locations/list.html`، `templates/locations/public.html`، `static/js/saved_locations.js`
- **ویرایش:** `core/capabilities.py`، `core/tests_capabilities.py` (فقط یک ردیف)، `config/settings.py`، `config/urls.py`، `utils/navigation.py`، `utils/media_views.py`، `people/services.py`، `templates/base.html`، `static/src/input.css`، `README.md`

### گام ۰ (فقط خواندن)
```
git status --short ; git log --oneline -5 ; git branch -a
python manage.py test            # تعداد کل تست را بنویس
ls locations                     # نباید وجود داشته باشد
```
شناسه‌ی آیکون‌ها را از sprite بگیر (`re.findall(r'<symbol id="([^"]+)"', ...)`). این‌ها باید باشند: `plus`، `copy`، `eye`، `pencil`، `trash-2`، `map-pin`، `check`، `x`. اگر یکی نبود، توقف و گزارش.
```
grep -n "bank_cards.manage\|tables.export" core/capabilities.py core/tests_capabilities.py
grep -n "NESHAN_API_KEY" utils/context_processors.py
```

### گام ۱: قابلیت
در `core/capabilities.py` زیر خط `"tables.export": _manager_or_accountant,` این خط را اضافه کن:
```python
    "locations.manage": _manager_or_accountant,   # موقعیت‌های ذخیره‌شده‌ی دلخواه و لینک عمومی‌شان
```
در `core/tests_capabilities.py` زیر `"tables.export": MGR_ACC,` این را بگذار (تنها ویرایش تستی این بریف):
```python
    "locations.manage": MGR_ACC,
```

### گام ۲: اپ `locations`
`locations/__init__.py` خالی. `locations/apps.py`:
```python
from django.apps import AppConfig


class LocationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'locations'
    verbose_name = 'موقعیت‌ها'
```
در `config/settings.py` زیر `'messenger',` اضافه کن: `'locations',`

`locations/models.py`:
```python
import uuid

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


def _new_token():
    return uuid.uuid4().hex


class SavedLocation(TimeStampedModel):
    """موقعیت دلخواه (انبار، دفتر، محل قرار). جدا از core.Location که مال پروژه‌هاست."""
    title = models.CharField(max_length=120, verbose_name="عنوان")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="عرض جغرافیایی")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="طول جغرافیایی")
    image = models.ImageField(upload_to="locations/", blank=True, verbose_name="تصویر")
    token = models.CharField(max_length=32, unique=True, default=_new_token, editable=False,
                             verbose_name="کد لینک عمومی")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+", verbose_name="ثبت‌کننده")

    class Meta:
        verbose_name = "موقعیت"
        verbose_name_plural = "موقعیت‌ها"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title
```
سپس `python manage.py makemigrations locations` را بزن و فایل ساخته‌شده را کامیت کن.

`locations/services.py`:
```python
import os
import uuid
from decimal import Decimal, InvalidOperation

from django.core.files.storage import default_storage
from django.db import transaction

from core.capabilities import can
from utils.image_utils import optimize_named
from .models import SavedLocation

TITLE_MAX = 120
DESCRIPTION_MAX = 2000
MAX_IMAGE_BYTES = 25 * 1024 * 1024   # هم‌سقف nginx
IMAGE_EXTS = ("jpg", "jpeg", "png", "webp")
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_QUANT = Decimal("0.000001")


def _require(actor):
    if not can(actor, "locations.manage"):
        raise ValueError("فقط مدیر یا حسابدار می‌تواند موقعیت‌ها را مدیریت کند.")


def parse_coordinate(raw, *, limit, label):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN).replace("٫", ".")
    if not text:
        raise ValueError(f"{label} را وارد کنید.")
    if "e" in text.lower():
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"{label} نامعتبر است؛ فقط عدد وارد کنید.")
    if not value.is_finite() or abs(value) > limit:
        raise ValueError(f"{label} باید بین {-limit} و {limit} باشد.")
    return value.quantize(_QUANT)


def _clean_title(raw):
    title = " ".join(str(raw or "").split())
    if not title:
        raise ValueError("عنوان را بنویسید.")
    if len(title) > TITLE_MAX:
        raise ValueError(f"عنوان نباید بیش از {TITLE_MAX} نویسه باشد.")
    return title


def _clean_description(raw):
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > DESCRIPTION_MAX:
        raise ValueError(f"توضیحات نباید بیش از {DESCRIPTION_MAX} نویسه باشد.")
    return text


def _prepare_image(uploaded):
    """فایل بهینه‌شده با نام تصادفی، یا ValueError فارسی. فقط JPG، PNG و WEBP."""
    name = os.path.basename((uploaded.name or "").replace("\\", "/"))[:255] or "image"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in IMAGE_EXTS:
        raise ValueError("تصویر باید JPG، PNG یا WEBP باشد.")
    if uploaded.size > MAX_IMAGE_BYTES:
        raise ValueError("حجم تصویر بیشتر از ۲۵ مگابایت است.")
    prepared, name = optimize_named(uploaded, name)   # تصویر جعلی ← ValueError فارسی
    prepared.name = f"{uuid.uuid4().hex}.{name.rsplit('.', 1)[-1].lower()}"
    return prepared


def _delete_after_commit(name):
    if name:
        transaction.on_commit(lambda: default_storage.delete(name))


def _clean_all(title, description, lat_raw, lng_raw, image):
    return (_clean_title(title), _clean_description(description),
            parse_coordinate(lat_raw, limit=90, label="عرض جغرافیایی"),
            parse_coordinate(lng_raw, limit=180, label="طول جغرافیایی"),
            _prepare_image(image) if image else None)


@transaction.atomic
def create_location(*, actor, title, description, lat_raw, lng_raw, image=None):
    _require(actor)
    title, description, lat, lng, prepared = _clean_all(title, description, lat_raw, lng_raw, image)
    place = SavedLocation(title=title, description=description, latitude=lat, longitude=lng, created_by=actor)
    if prepared is not None:
        place.image.save(prepared.name, prepared, save=False)
    place.save()
    return place


@transaction.atomic
def update_location(*, actor, location_id, title, description, lat_raw, lng_raw, image=None, remove_image=False):
    """کد لینک عمومی با ویرایش عوض نمی‌شود. image=None و remove_image=False یعنی تصویر دست نخورد."""
    _require(actor)
    title, description, lat, lng, prepared = _clean_all(title, description, lat_raw, lng_raw, image)
    place = SavedLocation.objects.select_for_update(of=("self",)).filter(pk=location_id).first()
    if place is None:
        raise ValueError("این موقعیت پیدا نشد؛ صفحه را تازه کنید.")
    old = place.image.name
    place.title, place.description, place.latitude, place.longitude = title, description, lat, lng
    if prepared is not None:
        place.image.save(prepared.name, prepared, save=False)
        _delete_after_commit(old)
    elif remove_image and old:
        place.image = ""
        _delete_after_commit(old)
    place.save()
    return place


@transaction.atomic
def delete_location(*, actor, location_id):
    _require(actor)
    place = SavedLocation.objects.select_for_update(of=("self",)).filter(pk=location_id).first()
    if place is None:
        raise ValueError("این موقعیت پیدا نشد؛ صفحه را تازه کنید.")
    _delete_after_commit(place.image.name)
    place.delete()
```

`locations/views.py`:
```python
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.capabilities import cap_required
from . import services
from .models import SavedLocation


def _run(work):
    try:
        work()
    except ValueError as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})


def _fields(request):
    p = request.POST
    return dict(title=p.get("title"), description=p.get("description"), lat_raw=p.get("latitude"),
                lng_raw=p.get("longitude"), image=request.FILES.get("image"))


@cap_required("locations.manage")
def location_list(request):
    places = list(SavedLocation.objects.all())
    for p in places:
        p.public_url = request.build_absolute_uri(reverse("locations:public", kwargs={"token": p.token}))
    return render(request, "locations/list.html", {"places": places})


@cap_required("locations.manage")
@require_POST
def location_create(request):
    return _run(lambda: services.create_location(actor=request.user, **_fields(request)))


@cap_required("locations.manage")
@require_POST
def location_update(request, pk):
    return _run(lambda: services.update_location(
        actor=request.user, location_id=pk, remove_image=request.POST.get("remove_image") == "1",
        **_fields(request)))


@cap_required("locations.manage")
@require_POST
def location_delete(request, pk):
    return _run(lambda: services.delete_location(actor=request.user, location_id=pk))


def public_location(request, token):
    """صفحه‌ی عمومی؛ بدون ورود. دسترسی فقط با کد حدس‌نزدنی (۳۲ نویسه‌ی هگز)."""
    place = get_object_or_404(SavedLocation, token=token)
    response = render(request, "locations/public.html", {
        "place": place,
        "image_url": reverse("locations:public_image", kwargs={"token": token}) if place.image else ""})
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Referrer-Policy"] = "no-referrer"
    return response


def public_location_image(request, token):
    place = get_object_or_404(SavedLocation, token=token)
    if not place.image:
        raise Http404
    try:
        handle = place.image.open("rb")
    except OSError:
        raise Http404
    response = FileResponse(handle, as_attachment=False)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=300"
    return response
```

`locations/urls.py`:
```python
from django.urls import path, re_path

from . import views

app_name = "locations"

urlpatterns = [
    path("locations/", views.location_list, name="list"),
    path("locations/new/", views.location_create, name="create"),
    path("locations/<int:pk>/save/", views.location_update, name="update"),
    path("locations/<int:pk>/delete/", views.location_delete, name="delete"),
    re_path(r"^loc/(?P<token>[0-9a-f]{32})/$", views.public_location, name="public"),
    re_path(r"^loc/(?P<token>[0-9a-f]{32})/image/$", views.public_location_image, name="public_image"),
]
```

### گام ۳: اتصال‌ها
**`config/urls.py`:** بالای خط `re_path(r'^media/...` این خط را اضافه کن:
```python
    path('', include('locations.urls', namespace='locations')),
```

**`utils/navigation.py`:**
- در `PAGE_PARENTS` زیر خط `"finance:bank_cards": ("home", [], {}),` اضافه کن: `"locations:list": ("home", [], {}),`
- در `NON_PAGE` (هر جای مجموعه) این‌ها را اضافه کن: `"locations:create", "locations:update", "locations:delete", "locations:public", "locations:public_image",`

**`utils/media_views.py`:** در `_allowed` درست قبل از `if head == "catalog":` اضافه کن:
```python
    if head == "locations":    # عکس موقعیت‌ها؛ عمومی فقط از locations:public_image با کد لینک
        return can(user, "locations.manage")
```

**`people/services.py`:** در `PAGE_LABELS` زیر `"finance:accounting_sale_new": "ثبت فروش",` اضافه کن: `"locations:list": "موقعیت‌ها",`

**`templates/base.html`:** در منوی آواتار، بعد از بلوک `{% if caps.bank_cards_manage %}...{% endif %}`:
```html
                            {% if caps.locations_manage %}
                            <li><a href="{% url 'locations:list' %}">{% icon "map-pin" "w-4 h-4" %} موقعیت‌ها</a></li>
                            {% endif %}
```

**`static/src/input.css`:** زیر `@source "../js/catalog_manage.js";` اضافه کن: `@source "../js/saved_locations.js";`

**`README.md`:** در جدول اپ‌ها زیر ردیف `messenger` اضافه کن:
`| \`locations\` | موقعیت‌های دلخواه مدیر و حسابدار با لینک نشان و صفحه‌ی عمومی (جدا از موقعیت پروژه‌ها) |`
و زنجیره‌ی وابستگی را به `... → tasks → messenger → locations` تغییر بده.

### گام ۴: تمپلیت لیست `templates/locations/list.html`
```html
{% extends "base.html" %}
{% load static custom_tags l10n %}
{% block title %}موقعیت‌ها | فرابخش{% endblock %}
{% block content %}
<div class="fb-page fb-page--lg">
    <div class="flex items-start justify-between gap-3 flex-wrap">
        <div>
            <h1 class="fb-page-title">موقعیت‌ها</h1>
            <p class="fb-page-sub">نقطه‌های دلخواه (مثل انبار، دفتر یا محل قرار) را ثبت کنید و لینکش را برای هر کسی بفرستید. این‌ها از موقعیت پروژه‌ها جدا هستند.</p>
        </div>
        <button type="button" class="btn btn-primary btn-sm" data-location-add data-url="{% url 'locations:create' %}">{% icon "plus" "w-4 h-4" %} افزودن موقعیت</button>
    </div>

    {% for p in places %}
    <article class="fb-card fb-pad flex flex-col gap-3">
        <div class="flex gap-3 min-w-0">
            {% if p.image %}<img src="{{ p.image.url }}" alt="{{ p.title }}" loading="lazy" class="w-24 h-24 shrink-0 object-cover rounded-field bg-base-300">{% endif %}
            <div class="min-w-0 flex flex-col gap-1">
                <h2 class="fb-section-title break-words">{{ p.title }}</h2>
                {% if p.description %}<p class="text-xs fb-muted whitespace-pre-line break-words line-clamp-3">{{ p.description }}</p>{% endif %}
                <span dir="ltr" class="text-xs fb-muted font-technical">{{ p.latitude|unlocalize }}, {{ p.longitude|unlocalize }}</span>
            </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
            <button type="button" class="btn btn-soft btn-sm" data-copy="{% map_url p.latitude p.longitude %}">{% icon "copy" "w-4 h-4" %} لینک نشان</button>
            <button type="button" class="btn btn-soft btn-sm" data-copy="{{ p.public_url }}">{% icon "copy" "w-4 h-4" %} لینک عمومی</button>
            <a href="{% url 'locations:public' token=p.token %}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">{% icon "eye" "w-4 h-4" %} صفحه‌ی عمومی</a>
            <button type="button" class="btn btn-ghost btn-sm" data-location-edit
                    data-url="{% url 'locations:update' p.pk %}" data-title="{{ p.title }}" data-description="{{ p.description }}"
                    data-lat="{{ p.latitude|unlocalize }}" data-lng="{{ p.longitude|unlocalize }}"
                    data-has-image="{% if p.image %}1{% else %}0{% endif %}">{% icon "pencil" "w-4 h-4" %} ویرایش</button>
            <button type="button" class="btn btn-soft btn-error btn-sm" data-location-delete
                    data-url="{% url 'locations:delete' p.pk %}" data-label="{{ p.title }}">{% icon "trash-2" "w-4 h-4" %} حذف</button>
        </div>
    </article>
    {% empty %}
    <div class="fb-card"><div class="fb-empty">هنوز موقعیتی ثبت نشده. با دکمه‌ی «افزودن موقعیت» شروع کنید.</div></div>
    {% endfor %}
</div>

<dialog id="location-dialog" class="modal" data-map-key="{{ NESHAN_API_KEY }}">
    <div class="modal-box max-w-lg">
        <h3 class="font-bold text-base mb-4" data-form-title>موقعیت جدید</h3>
        <form data-location-form class="flex flex-col gap-4" novalidate>
            <div class="fb-field">
                <label class="fb-label" for="loc-title">عنوان</label>
                <input type="text" id="loc-title" name="title" maxlength="120" autocomplete="off" class="input w-full">
            </div>
            <div class="fb-field">
                <label class="fb-label" for="loc-description">توضیحات</label>
                <textarea id="loc-description" name="description" rows="3" maxlength="2000" class="textarea w-full"></textarea>
            </div>
            <div class="fb-field">
                <label class="fb-label" for="loc-image">تصویر (در صورت نیاز)</label>
                <input type="file" id="loc-image" name="image" accept="image/jpeg,image/png,image/webp" class="file-input w-full">
                <span class="fb-hint">JPG، PNG یا WEBP؛ خودکار کوچک می‌شود.</span>
                <div class="hidden" data-remove-image-box>
                    <label class="flex items-center gap-2 text-sm cursor-pointer">
                        <input type="checkbox" name="remove_image" value="1" class="checkbox checkbox-sm"> حذف تصویر فعلی
                    </label>
                </div>
            </div>

            <div class="fb-field">
                <span class="fb-label">موقعیت</span>
                {% if NESHAN_API_KEY %}
                <div id="location-map" class="h-64 rounded-field overflow-hidden"></div>
                {% else %}
                <div role="alert" class="alert alert-soft alert-warning">
                    {% icon "alert-triangle" "w-4 h-4 shrink-0" %}
                    <span class="text-xs">کلید نقشه تنظیم نشده؛ از «موقعیت من» یا مختصات دستی استفاده کنید.</span>
                </div>
                {% endif %}
                <span class="fb-hint">روی نقشه بزنید تا نقطه‌ی پیشنهادی بیاید. موقعیت ثبت‌شده فقط با «تایید این نقطه» عوض می‌شود.</span>
            </div>
            <div class="flex flex-wrap items-center gap-2">
                <button type="button" class="btn btn-soft btn-sm" data-my-location>{% icon "map-pin" "w-4 h-4" %} موقعیت من</button>
            </div>
            <div class="grid grid-cols-2 gap-2">
                <div class="fb-field">
                    <label class="fb-label" for="loc-manual-lat">عرض جغرافیایی</label>
                    <input type="text" id="loc-manual-lat" data-decimal dir="ltr" inputmode="decimal" autocomplete="off" placeholder="36.297900" class="input input-sm w-full font-technical">
                </div>
                <div class="fb-field">
                    <label class="fb-label" for="loc-manual-lng">طول جغرافیایی</label>
                    <input type="text" id="loc-manual-lng" data-decimal dir="ltr" inputmode="decimal" autocomplete="off" placeholder="59.606200" class="input input-sm w-full font-technical">
                </div>
            </div>
            <button type="button" class="btn btn-ghost btn-sm self-start" data-manual-apply>نمایش این مختصات روی نقشه</button>

            <div class="hidden" data-candidate-box>
                <div class="fb-inset flex flex-wrap items-center justify-between gap-2">
                    <span class="text-sm">نقطه‌ی پیشنهادی: <span dir="ltr" class="font-technical" data-candidate-text></span></span>
                    <div class="flex gap-2">
                        <button type="button" class="btn btn-primary btn-sm" data-candidate-confirm>تایید این نقطه</button>
                        <button type="button" class="btn btn-ghost btn-sm" data-candidate-cancel>انصراف</button>
                    </div>
                </div>
            </div>
            <div class="fb-inset flex items-center justify-between gap-2 text-sm">
                <span class="fb-muted">موقعیت ثبت‌شده</span>
                <span dir="ltr" class="font-technical" data-confirmed-text>—</span>
            </div>
            <input type="hidden" name="latitude">
            <input type="hidden" name="longitude">

            <p class="fb-error hidden" data-form-error></p>
            <div class="flex gap-2">
                <button type="submit" class="btn btn-primary flex-1" data-form-submit>ثبت</button>
                <button type="button" class="btn btn-ghost flex-1" data-form-cancel>انصراف</button>
            </div>
        </form>
    </div>
    <form method="dialog" class="modal-backdrop"><button>close</button></form>
</dialog>

<dialog id="location-delete-dialog" class="modal">
    <div class="modal-box max-w-sm">
        <h3 class="font-bold text-base mb-2">حذف موقعیت</h3>
        <p class="text-sm">موقعیت «<span data-delete-label class="font-semibold"></span>» حذف شود؟ لینک عمومی‌اش هم از کار می‌افتد و برگشت ندارد.</p>
        <p class="fb-error hidden mt-2" data-delete-error></p>
        <div class="flex gap-2 pt-4">
            <button type="button" class="btn btn-soft btn-error flex-1" data-delete-ok>حذف</button>
            <button type="button" class="btn btn-ghost flex-1" onclick="this.closest('dialog').close()">انصراف</button>
        </div>
    </div>
    <form method="dialog" class="modal-backdrop"><button>close</button></form>
</dialog>
{% endblock %}

{% block extra_js %}
<script src="{% static_v 'js/uploader.js' %}"></script>
<script src="{% static_v 'js/saved_locations.js' %}"></script>
{% endblock %}
```

### گام ۵: صفحه‌ی عمومی `templates/locations/public.html`
```html
{% extends "base.html" %}
{% load static custom_tags %}
{% block title %}{{ place.title }} | فرابخش تهویه{% endblock %}
{% block extra_head %}<meta name="robots" content="noindex, nofollow">{% endblock %}
{% block content %}
<div class="fb-page fb-page--sm">
    <div class="flex items-center gap-2">
        <img src="{% static 'icons/logo.svg' %}" alt="" class="w-9 h-9 object-contain bg-white rounded-field p-1 border border-base-300">
        <span class="text-sm font-bold text-primary">فرابخش تهویه</span>
    </div>
    <section class="fb-card fb-pad flex flex-col gap-4">
        <h1 class="fb-page-title break-words">{{ place.title }}</h1>
        {% if image_url %}<img src="{{ image_url }}" alt="{{ place.title }}" class="w-full max-h-80 object-cover rounded-field bg-base-300">{% endif %}
        {% if place.description %}<p class="text-sm whitespace-pre-line break-words leading-7">{{ place.description }}</p>{% endif %}
        {% include "projects/partials/map_actions.html" with location=place %}
    </section>
</div>
{% endblock %}
{% block extra_js %}<script src="{% static_v 'js/route_link.js' %}"></script>{% endblock %}
```

### گام ۶: `static/js/saved_locations.js`
فقط `createElement` و `textContent` مجاز است. هیچ متنی از سرور یا کاربر نباید با روش‌های ممنوع (طبق قواعد ثابت) وارد صفحه شود، حتی در کامنت.
```javascript
(function () {
  var dlg = document.getElementById('location-dialog');
  if (!dlg) return;
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var DEFAULT = { lat: 36.2979, lng: 59.6062 };
  var SDK = 'https://static.neshan.org/sdk/maplibre/5.24.3/neshan-maplibre-sdk';
  var STYLE = 'https://static.neshan.org/sdk/maplibre/styles/light.json';
  var form = dlg.querySelector('[data-location-form]');
  function q(sel) { return dlg.querySelector(sel); }
  var els = {
    heading: q('[data-form-title]'), error: q('[data-form-error]'), submit: q('[data-form-submit]'),
    candBox: q('[data-candidate-box]'), candText: q('[data-candidate-text]'), confText: q('[data-confirmed-text]'),
    removeBox: q('[data-remove-image-box]'), manLat: q('#loc-manual-lat'), manLng: q('#loc-manual-lng'),
    title: form.querySelector('[name="title"]'), description: form.querySelector('[name="description"]'),
    lat: form.querySelector('[name="latitude"]'), lng: form.querySelector('[name="longitude"]')
  };
  var state = { action: '', confirmed: null, candidate: null, map: null, gl: null, markers: {}, sdk: null };

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function fmt(pt) { return pt.lat.toFixed(6) + ', ' + pt.lng.toFixed(6); }
  function say(text) { els.error.textContent = text || ''; els.error.classList.toggle('hidden', !text); }

  function paintCandidate() {
    els.candBox.classList.toggle('hidden', !state.candidate);
    els.candText.textContent = state.candidate ? fmt(state.candidate) : '';
  }
  function paintConfirmed() {
    els.confText.textContent = state.confirmed ? fmt(state.confirmed) : '—';
    els.lat.value = state.confirmed ? state.confirmed.lat.toFixed(6) : '';
    els.lng.value = state.confirmed ? state.confirmed.lng.toFixed(6) : '';
  }

  // ---------- نقشه (فقط وقتی کلید نشان هست) ----------
  function loadSdk() {
    if (state.sdk) return state.sdk;
    state.sdk = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = SDK + '.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = SDK + '.umd.js';
      s.onload = function () { resolve((window.maplibregl && window.maplibregl.default) || window.maplibregl); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return state.sdk;
  }
  function syncMarkers() {
    if (!state.map) return;
    [['confirmed', state.confirmed, {}], ['candidate', state.candidate, { color: '#B45309' }]].forEach(function (m) {
      if (state.markers[m[0]]) { state.markers[m[0]].remove(); state.markers[m[0]] = null; }
      if (m[1]) state.markers[m[0]] = new state.gl.Marker(m[2]).setLngLat([m[1].lng, m[1].lat]).addTo(state.map);
    });
  }
  function ensureMap() {
    var box = document.getElementById('location-map');
    if (!box || !dlg.dataset.mapKey) return Promise.resolve(null);
    if (state.map) return Promise.resolve(state.map);
    return loadSdk().then(function (gl) {
      state.gl = gl;
      state.map = new gl.Map({ container: box, style: STYLE, center: [DEFAULT.lng, DEFAULT.lat], zoom: 12, apiKey: dlg.dataset.mapKey });
      state.map.addControl(new gl.NavigationControl());
      state.map.on('click', function (e) { setCandidate(e.lngLat.lat, e.lngLat.lng, false); });   // فقط پیشنهاد؛ ثبت نمی‌شود
      return state.map;
    }, function () { say('نقشه بارگذاری نشد؛ مختصات را دستی بنویسید.'); return null; });
  }

  // ---------- نقطه‌ی پیشنهادی ← تایید ----------
  function setCandidate(lat, lng, fly) {
    state.candidate = { lat: lat, lng: lng };
    els.manLat.value = lat.toFixed(6);
    els.manLng.value = lng.toFixed(6);
    paintCandidate();
    syncMarkers();
    if (fly && state.map) state.map.flyTo({ center: [lng, lat], zoom: 16 });
  }
  q('[data-candidate-confirm]').addEventListener('click', function () {
    if (!state.candidate) return;
    state.confirmed = state.candidate;
    state.candidate = null;
    say('');
    paintCandidate();
    paintConfirmed();
    syncMarkers();
  });
  q('[data-candidate-cancel]').addEventListener('click', function () {
    state.candidate = null;
    paintCandidate();
    syncMarkers();
  });
  q('[data-manual-apply]').addEventListener('click', function () {
    var lat = parseFloat(els.manLat.value), lng = parseFloat(els.manLng.value);
    if (isNaN(lat) || isNaN(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      say('مختصات را درست بنویسید: عرض بین ۹۰- تا ۹۰ و طول بین ۱۸۰- تا ۱۸۰.');
      return;
    }
    say('');
    setCandidate(lat, lng, true);
  });
  q('[data-my-location]').addEventListener('click', function () {
    var btn = this;
    if (!navigator.geolocation) { say('این مرورگر موقعیت‌یابی را پشتیبانی نمی‌کند؛ روی نقشه بزنید یا مختصات را بنویسید.'); return; }
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function (pos) {
      btn.disabled = false;
      say('');
      setCandidate(pos.coords.latitude, pos.coords.longitude, true);
    }, function () {
      btn.disabled = false;
      say('موقعیت شما پیدا نشد؛ اجازه‌ی مرورگر را بررسی کنید یا روی نقشه بزنید.');
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });

  // ---------- باز کردن فرم ----------
  function openForm(o) {
    form.reset();
    state.action = o.url;
    els.heading.textContent = o.heading;
    els.title.value = o.title || '';
    els.description.value = o.description || '';
    els.removeBox.classList.toggle('hidden', !o.hasImage);
    els.manLat.value = '';
    els.manLng.value = '';
    state.candidate = null;
    state.confirmed = (o.lat && o.lng) ? { lat: parseFloat(o.lat), lng: parseFloat(o.lng) } : null;
    paintCandidate();
    paintConfirmed();
    say('');
    els.submit.disabled = false;
    els.submit.textContent = 'ثبت';
    dlg.showModal();
    ensureMap().then(function (map) {
      if (!map) return;
      map.resize();
      var c = state.confirmed || DEFAULT;
      map.jumpTo({ center: [c.lng, c.lat], zoom: state.confirmed ? 15 : 12 });
      syncMarkers();
    });
  }
  q('[data-form-cancel]').addEventListener('click', function () { dlg.close(); });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (state.candidate) { say('نقطه‌ی پیشنهادی هنوز تایید نشده؛ «تایید این نقطه» یا «انصراف» را بزنید.'); return; }
    if (!state.confirmed) { say('ابتدا یک نقطه را روی نقشه انتخاب و تایید کنید.'); return; }
    if (!els.title.value.trim()) { say('عنوان را بنویسید.'); return; }
    say('');
    els.submit.disabled = true;
    window.fbSend(state.action, new FormData(form), window.FB_CSRF, function (p) {
      els.submit.textContent = p < 100 ? fa(p) + '٪' : 'در حال ثبت...';
    }).then(function (res) {
      if (res.ok) { window.location.reload(); return; }
      els.submit.disabled = false;
      els.submit.textContent = 'ثبت';
      say(res.error || 'ثبت نشد.');
    });
  });

  // ---------- دکمه‌های صفحه (تفویضی) ----------
  var delDlg = document.getElementById('location-delete-dialog');
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-location-add],[data-location-edit],[data-location-delete],[data-delete-ok]') : null;
    if (!t) return;
    if (t.hasAttribute('data-location-add')) {
      openForm({ url: t.dataset.url, heading: 'موقعیت جدید' });
    } else if (t.hasAttribute('data-location-edit')) {
      var d = t.dataset;
      openForm({ url: d.url, heading: 'ویرایش موقعیت', title: d.title, description: d.description,
                 lat: d.lat, lng: d.lng, hasImage: d.hasImage === '1' });
    } else if (t.hasAttribute('data-location-delete')) {
      delDlg.querySelector('[data-delete-label]').textContent = t.dataset.label;
      delDlg.querySelector('[data-delete-error]').classList.add('hidden');
      var okBtn = delDlg.querySelector('[data-delete-ok]');
      okBtn.dataset.url = t.dataset.url;
      okBtn.disabled = false;
      delDlg.showModal();
    } else if (t.hasAttribute('data-delete-ok') && t.dataset.url) {
      var err = delDlg.querySelector('[data-delete-error]');
      t.disabled = true;
      window.fbSend(t.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        t.disabled = false;
        err.textContent = res.error || 'حذف نشد.';
        err.classList.remove('hidden');
      });
    }
  });
})();
```

### گام ۷: ساخت و بررسی
```
python manage.py makemigrations locations
python manage.py makemigrations --check --dry-run
pnpm run build
python manage.py test        # بدون هیچ تست تازه؛ فقط تعداد قبل و بعد
```
`git diff --stat` را بگیر. فقط فایل‌های بالا باید عوض شده باشند.

### Mutation
در این بریف تست تازه نداریم. mutationها در بریف ۳ اجرا می‌شوند.

### گزارش خواسته‌شده
تعداد تست قبل و بعد (باید یکی باشد)، خروجی `makemigrations --check --dry-run`، گواهی `pnpm run build`، فهرست فایل‌ها، انحراف‌ها، `git log --oneline -3`، `git branch -a`. گزارش جایگزین تست دستی نیست.

### تست دستی کاربر
۱. با مدیر و حسابدار: در منوی آواتار «موقعیت‌ها» کنار «کارت‌های بانکی» باشد. پذیرش، تکنسین و مشتری آن را نبینند.
۲. «افزودن موقعیت» را بزن و روی نقشه کلیک کن. نقطه‌ی نارنجی با «تایید این نقطه / انصراف» بیاید و «موقعیت ثبت‌شده» عوض نشود.
۳. با نقطه‌ی تاییدنشده «ثبت» را بزن؛ پیام «هنوز تایید نشده» بیاید. بعد تایید کن و ثبت کن؛ کارت بیاید.
۴. مختصات را دستی بنویس، «نمایش» بزن و تایید کن. «موقعیت من» را هم امتحان کن.
۵. «لینک نشان» را کپی و باز کن (اپ نشان یا وب نشان باید روی نقطه باز شود). «لینک عمومی» را در پنجره‌ی ناشناس باز کن: عنوان، توضیحات و تصویر با دو دکمه‌ی «مشاهده روی نقشه» و «مسیریابی با ماشین».
۶. ویرایش: عنوان و تصویر را عوض کن، «حذف تصویر فعلی» را امتحان کن. حذف: کارت برود و لینک عمومی ۴۰۴ بدهد.
۷. روشن و تاریک و موبایل را ببین.

### پرسش غیرمسدود
لینک عمومی الان فقط با حذف موقعیت از کار می‌افتد. آیا «غیرفعال‌کردن لینک عمومی» یا «ساخت لینک تازه» هم لازم است؟

### موکول
چرخش کد لینک، غیرفعال‌کردن لینک، جستجو در لیست.
