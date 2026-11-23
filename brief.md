# بریف ۱۱: واحد هر ردیف در پیش‌فاکتور (کنار مقدار)

شاخه: `feat/line-units` (از `main` تازه). بلوک «قواعد ثابت» را کاربر اول نشست داده است.

## توضیح ساده

الان ردیف خدمت فقط «مقدار» دارد. نمی‌شود فهمید ۲۰ کانال یعنی ۲۰ عدد یا ۲۰ متر یا ۲۰ متر مربع. می‌خواهیم کنار مقدار یک انتخاب «واحد» باشد و واحد به این شکل کار کند:

۱. در ویرایشگر هر ردیف خدمت، کنار مقدار یک انتخاب واحد هست (متر، متر مربع، متر مکعب، لیتر، کیلوگرم، عدد). با انتخاب خدمت، واحد پیش‌فرض همان خدمت خودکار می‌آید و حسابدار هر ردیف را جدا عوض می‌کند. یک خدمت در یک پروژه با «عدد» و در پروژه‌ی دیگر با «متر» فروخته می‌شود.
۲. واحد برای ردیف خدمت اجباری است. اگر خدمت واحد پیش‌فرض نداشته باشد و کاربر انتخاب نکند، خطا می‌گیرد: «واحد «کانال» را انتخاب کنید.»
۳. ردیف «اضافه یا تخفیف» هم واحد دارد، ولی خالی ماندنش مجاز است («بدون واحد»).
۴. واحد هنگام صدور روی ردیف فاکتور کپی می‌شود (قانون طلایی ۱) و در PDF فاکتور، صفحه‌ی فاکتور مشتری، پیش‌نمایش قبل از صدور، صفحه‌ی فاکتور حسابدار، پرونده‌ی مالی و بازبینی نهایی کنار مقدار نشان داده می‌شود.
۵. مودال «قدیم ← جدید» تغییر واحد را هم نشان می‌دهد.

## گام ۰ (فقط خواندن)

```
git status --short
git log --oneline -5
git checkout main && git pull && git checkout -b feat/line-units
grep -n "class ProjectService\|class ProjectExtraLine\|^from\|^import" projects/models.py | head -30
grep -n "class InvoiceLine\|^from\|^import" finance/models.py | head -20
grep -n "def _make_line\|def build_invoice_lines" finance/services.py
grep -n "SERVICE_COLS\|EXTRA_COLS\|^from catalog" projects/proforma.py
grep -n "unit" projects/proforma_rows.py
grep -rn "\.qty" templates/ | grep -v "sale\|stock\|usage\|movement"
grep -n "unit" projects/confirmations.py templates/projects/partials/stage_install.html
```
- در `projects/proforma_rows.py` نباید `unit` (به‌جز `unit_price`) باشد.
- فهرست `grep -rn "\.qty"` را در گزارش بیاور. هر جایی که ردیف **فاکتور یا پیش‌فاکتور** را چاپ می‌کند و در این بریف نیامده، گزارش کن.
- تعداد تست قبل از شروع را بگیر.

## گام ۱: مدل‌ها

### `projects/models.py`

زیر `from core.models import TimeStampedModel` اضافه کن:
```python
from catalog.models import Item

UNIT_LABELS = dict(Item.Unit.choices)
```

در `ProjectService` بعد از خط `qty = ...`:
```python
    unit = models.CharField(max_length=20, choices=Item.Unit.choices, blank=True, verbose_name="واحد")
```
و بعد از property `total` همان کلاس:
```python
    @property
    def unit_code(self):
        """واحد این ردیف؛ اگر ثبت نشده باشد واحد پیش‌فرض خدمت."""
        return self.unit or self.service.unit

    @property
    def unit_label(self):
        return UNIT_LABELS.get(self.unit_code, "")
```

در `ProjectExtraLine` بعد از خط `qty = ...`:
```python
    unit = models.CharField(max_length=20, choices=Item.Unit.choices, blank=True, verbose_name="واحد")
```
و داخل کلاس یک property:
```python
    @property
    def unit_label(self):
        return UNIT_LABELS.get(self.unit, "")
```

### `finance/models.py`

بالای فایل `from catalog.models import Item` را اضافه کن. در `InvoiceLine` بعد از `qty`:
```python
    unit = models.CharField(max_length=20, choices=Item.Unit.choices, blank=True, verbose_name="واحد (کپی در لحظه‌ی صدور)")
```

### مایگریشن‌ها

```
python manage.py makemigrations projects -n service_line_units
python manage.py makemigrations finance -n invoice_line_unit
python manage.py makemigrations --check --dry-run
```
خروجی آخر باید «No changes detected» باشد. مایگریشن داده نمی‌نویسیم: ردیف‌های قدیمی واحد خالی می‌مانند و `unit_code` برای ردیف خدمت به واحد پیش‌فرض خدمت برمی‌گردد.

## گام ۲: `finance/services.py`

`_make_line` را کامل جایگزین کن:
```python
def _make_line(invoice, line_type, title, qty, unit_price, cost_snapshot=None, unit=""):
    return InvoiceLine(
        invoice=invoice,
        line_type=line_type,
        title=title,
        qty=qty,
        unit=unit,
        unit_price=unit_price,
        cost_snapshot=cost_snapshot,
        total=qty * unit_price,
    )
```

در `build_invoice_lines`:

قدیم:
```python
        line = _make_line(invoice, InvoiceLine.LineType.SERVICE, ps.service.name, ps.qty, ps.unit_price)
```
جدید:
```python
        line = _make_line(invoice, InvoiceLine.LineType.SERVICE, ps.service.name, ps.qty, ps.unit_price,
                          unit=ps.unit_code)
```

قدیم:
```python
        _make_line(invoice, InvoiceLine.LineType.MATERIAL, pm.item.name, pm.qty, pm.unit_price, pm.item.moving_average_cost)
```
جدید:
```python
        _make_line(invoice, InvoiceLine.LineType.MATERIAL, pm.item.name, pm.qty, pm.unit_price,
                   pm.item.moving_average_cost, unit=pm.item.unit)
```

قدیم:
```python
            lines.append(_make_line(invoice, InvoiceLine.LineType.DISCOUNT, xl.title, xl.qty, -xl.unit_price))
        else:
            lines.append(_make_line(invoice, InvoiceLine.LineType.EXTRA, xl.title, xl.qty, xl.unit_price))
```
جدید:
```python
            lines.append(_make_line(invoice, InvoiceLine.LineType.DISCOUNT, xl.title, xl.qty, -xl.unit_price,
                                    unit=xl.unit))
        else:
            lines.append(_make_line(invoice, InvoiceLine.LineType.EXTRA, xl.title, xl.qty, xl.unit_price,
                                    unit=xl.unit))
```
(ردیف‌های نصب، ارسال و مازاد جمعی `qty=1` دارند و بدون واحد می‌مانند.)

## گام ۳: `projects/proforma.py`

بعد از تعریف `MATERIAL_COLS` اضافه کن:
```python
UNIT_CHOICES = tuple(Item.Unit.values)
```

`SERVICE_COLS` را این کن (ستون `unit` بین `qty` و `unit_price`، با `required=False` تا اجباری‌بودنش را در سرویس با پیام فارسی خوب بگیریم):
```python
SERVICE_COLS = (
    Col("service_id", "خدمت", "picker"),
    Col("qty", "مقدار خدمت", "number", positive=True),
    Col("unit", "واحد", "select", required=False, choices=UNIT_CHOICES),
    Col("unit_price", "قیمت خود خدمت (تومان)", "money"),
)
```
`EXTRA_COLS` را این کن:
```python
EXTRA_COLS = (
    Col("title", "شرح", "text", max_len=200),
    Col("kind", "نوع", "select", choices=("extra", "discount")),
    Col("qty", "مقدار", "number", positive=True),
    Col("unit", "واحد", "select", required=False, choices=UNIT_CHOICES),
    Col("unit_price", "مبلغ واحد (تومان)", "money", positive=True),
)
```

مسیر قدیمی `save_proforma` هنوز در کد است. دو خط را همگام کن:

در `_sync_extra_rows` قدیم:
```python
        line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
```
جدید:
```python
        line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
        line.unit = row.get("unit") or ""
```
در `_sync_service_rows` قدیم:
```python
        line.service_id, line.qty, line.unit_price = row["service_id"], qty, row["unit_price"]
```
جدید:
```python
        line.service_id, line.qty, line.unit_price = row["service_id"], qty, row["unit_price"]
        line.unit = row.get("unit") or ""
```

## گام ۴: `projects/proforma_rows.py`

**۴-الف)** ایمپورت: `from .models import Project, ProjectExtraLine, ProjectService` را این کن:
```python
from .models import Project, ProjectExtraLine, ProjectService, UNIT_LABELS
```

**۴-ب)** بعد از تابع `_int` تابع تازه را اضافه کن:
```python
def _resolve_unit(raw, service):
    """واحد ردیف خدمت: انتخاب کاربر، وگرنه واحد پیش‌فرض خدمت؛ هیچ‌کدام نبود خطا."""
    code = raw or service.unit or ""
    if not code:
        raise ValueError(f"واحد «{service.name}» را انتخاب کنید.")
    return code
```

**۴-ج)** `service_row_initial` و `extra_row_initial` را کامل جایگزین کن:
```python
def service_row_initial(line):
    q = lambda v: format(Decimal(v).normalize(), "f")
    saved = sorted(line.materials.all(), key=lambda m: m.pk)
    have = {m.item_id for m in saved}
    mats = [{"pk": m.pk, "item_id": m.item_id, "on": True} for m in saved]
    mats += [{"item_id": b.item_id, "on": False} for b in line.service.bom_lines.all()
             if b.item_id not in have and b.item.is_active]
    return {"pk": line.pk, "service_id": line.service_id, "qty": q(line.qty), "unit": line.unit_code,
            "unit_price": str(int(line.unit_price)), "materials": mats}


def extra_row_initial(x):
    return {"pk": x.pk, "title": x.title, "kind": x.kind, "qty": format(Decimal(x.qty).normalize(), "f"),
            "unit": x.unit, "unit_price": str(int(x.unit_price))}
```

**۴-د)** `save_service_line`:

قدیم:
```python
    if not Service.objects.filter(pk=row["service_id"]).exists():
        raise ValueError("خدمت انتخاب‌شده در سیستم پیدا نشد.")
    qty = row["qty"].quantize(Decimal("0.01"))
    if qty <= 0:
        raise ValueError("مقدار خدمت خیلی کوچک است.")
    line = _line_or_none(project.services.all(), row["pk"]) or ProjectService(project=project)
    check_material_items(project, row["materials"])
    line.service_id, line.qty, line.unit_price = row["service_id"], qty, row["unit_price"]
```
جدید:
```python
    service = Service.objects.filter(pk=row["service_id"]).first()
    if service is None:
        raise ValueError("خدمت انتخاب‌شده در سیستم پیدا نشد.")
    unit = _resolve_unit(row.get("unit"), service)
    qty = row["qty"].quantize(Decimal("0.01"))
    if qty <= 0:
        raise ValueError("مقدار خدمت خیلی کوچک است.")
    line = _line_or_none(project.services.all(), row["pk"]) or ProjectService(project=project)
    check_material_items(project, row["materials"])
    line.service_id, line.qty, line.unit, line.unit_price = row["service_id"], qty, unit, row["unit_price"]
```

**۴-ه)** `save_extra_line`:

قدیم:
```python
    line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
    line.save()
    _refresh_invoice(project)
    return line
```
جدید (دقت: این بلوک در `save_extra_line` است، نه در `save_service_line`):
```python
    line.kind, line.title, line.qty, line.unit_price = row["kind"], row["title"], qty, row["unit_price"]
    line.unit = row.get("unit") or ""
    line.save()
    _refresh_invoice(project)
    return line
```

**۴-و)** پیش‌نمایش «چه به چه»:

در `_old_view` در دیکشنری بازگشتی بعد از `"name": line.service.name,` این را اضافه کن: `"unit": line.unit_label,`.

در `_new_view` بعد از بررسی `if service is None: raise ...` اضافه کن:
```python
    unit = _resolve_unit(row.get("unit"), service)
```
و در دیکشنری بازگشتی بعد از `"qty": qty,` اضافه کن: `"unit": UNIT_LABELS.get(unit, ""),`.

در `_diff_service` بعد از شرط مقدار (`if old["qty"] != new["qty"]: ...`) اضافه کن:
```python
    if old["unit"] != new["unit"]:
        out.append(_change("واحد", old["unit"] or "—", new["unit"] or "—"))
```

`_extra_view` را کامل جایگزین کن:
```python
def _extra_view(kind, title, qty, unit_price, unit=""):
    t = _round0(Decimal(qty) * Decimal(unit_price))
    return {"kind": kind, "title": title, "qty": Decimal(qty), "unit": UNIT_LABELS.get(unit or "", ""),
            "unit_price": Decimal(unit_price),
            "total": -t if kind == ProjectExtraLine.Kind.DISCOUNT else t}
```
در `_diff_extra` بعد از شرط مقدار اضافه کن:
```python
    if old["unit"] != new["unit"]:
        out.append(_change("واحد", old["unit"] or "—", new["unit"] or "—"))
```
در `preview_change` (شاخه‌ی `kind == "extra"`):

قدیم:
```python
        new = _extra_view(row["kind"], row["title"], qty, row["unit_price"])
```
جدید:
```python
        new = _extra_view(row["kind"], row["title"], qty, row["unit_price"], row.get("unit") or "")
```
قدیم:
```python
        old = _extra_view(line.kind, line.title, line.qty, line.unit_price)
```
جدید:
```python
        old = _extra_view(line.kind, line.title, line.qty, line.unit_price, line.unit)
```

## گام ۵: `projects/views.py` و `projects/confirmations.py`

در `_proforma_context`:

قدیم:
```python
        "services_data": [{"id": s.id, "name": s.name, "unit": s.get_unit_display() if s.unit else "",
                           "items": defaults.get(s.id, [])} for s in services],
```
جدید:
```python
        "services_data": [{"id": s.id, "name": s.name, "unit": s.get_unit_display() if s.unit else "",
                           "unit_value": s.unit, "items": defaults.get(s.id, [])} for s in services],
        "units_data": [list(c) for c in Item.Unit.choices],
```
(`Item` در همین فایل ایمپورت است.)

در `projects/confirmations.py::shipped_services` قدیم:
```python
             "unit": ps.service.get_unit_display() if ps.service.unit else ""}
```
جدید:
```python
             "unit": ps.unit_label}
```

## گام ۶: جاوااسکریپت

### `static/js/line_editor.js`

در شاخه‌ی `col.type === 'select'` بعد از خط `cell.get = function () { return sel.value; };` اضافه کن:
```js
      cell.set = function (v) { sel.value = v; };
```

### `static/js/proforma_page.js`

بعد از تابع `data(id)` (بالای فایل) اضافه کن:
```js
  function unitOptions(emptyLabel) { return [['', emptyLabel]].concat(data('units-data')); }
```
در `serviceSpec`، داخل `fillDefaults` اولین خط بدنه (قبل از `var kids = row.children`) این باشد:
```js
      if (svc.unit_value && row.cells.unit && row.cells.unit.set) row.cells.unit.set(svc.unit_value);
```
در `columns` همان تابع بین `qty` و `unit_price` اضافه کن:
```js
        { key: 'unit', type: 'select', label: 'واحد', cls: 'w-36', options: unitOptions('انتخاب واحد') },
```
در `extraSpec` بین `qty` و `unit_price` اضافه کن:
```js
        { key: 'unit', type: 'select', label: 'واحد', cls: 'w-32', options: unitOptions('بدون واحد') },
```
(بدون `innerHTML` و مشابه؛ فقط `createElement/textContent` که موتور قبلاً دارد. نیازی به `@source` تازه نیست.)

## گام ۷: قالب‌ها

### `templates/projects/partials/proforma_body.html`
- پایین فایل، کنار `{{ items_data|json_script:"items-data" }}` اضافه کن: `{{ units_data|json_script:"units-data" }}`.
- ردیف خدمت (متغیر `s`):
  قدیم: `<td class="text-center font-technical">{{ s.line.qty|floatformat:"-2"|fa_digits }}</td>`
  جدید: `<td class="text-center"><span class="font-technical">{{ s.line.qty|floatformat:"-2"|fa_digits }}</span>{% if s.line.unit_label %} {{ s.line.unit_label }}{% endif %}</td>`
- ردیف اضافه/تخفیف (متغیر `x`): همان تغییر با `x.line.qty` و `x.line.unit_label`.
- ردیف دستی فاکتور (متغیر `l`) را دست نزن.

### `templates/projects/partials/proforma_preview.html`
- بین `<th ...>مقدار</th>` و `<th ...>مبلغ واحد (تومان)</th>` اضافه کن: `<th class="text-center font-medium">واحد</th>`
- در ردیف، بعد از td مقدار اضافه کن: `<td class="text-center">{{ l.get_unit_display|default:"—" }}</td>`

### `templates/finance/portal_invoice.html`
- بعد از `<th class="text-center font-medium">مقدار</th>` اضافه کن: `<th class="text-center font-medium">واحد</th>`
- بعد از td مقدار (`{{ line.qty|floatformat:"-2"|fa_digits }}`) اضافه کن: `<td class="text-center">{{ line.get_unit_display|default:"—" }}</td>`
- `colspan="5"` در ردیف خالی را `colspan="6"` کن.

### `templates/finance/invoice_pdf.html`
- عرض ستون‌ها: ردیف ۷٪، شرح ۴۰٪، مقدار ۱۱٪، **واحد ۱۰٪ (ستون تازه بعد از مقدار)**، مبلغ واحد ۱۶٪، جمع کل ۱۶٪. هدر ستون تازه: `<th style="width: 10%;">واحد</th>`.
- در ردیف بعد از td مقدار (`<td class="num-col">{{ line.qty|floatformat:"-2"|fa_digits }}</td>`) اضافه کن: `<td>{{ line.get_unit_display|default:"—" }}</td>`
- `colspan="5"` ردیف خالی را `colspan="6"` کن.
- حلقه (`invoice.lines.all` یا `lines`، بسته به اجرای بریف ۱۰) را دست نزن.

### `templates/finance/accounting_project.html` (جدول ردیف‌های فاکتور)
قدیم: `<td class="font-technical">{{ l.qty|floatformat:"-2"|fa_digits }}</td>`
جدید: `<td><span class="font-technical">{{ l.qty|floatformat:"-2"|fa_digits }}</span>{% if l.unit %} {{ l.get_unit_display }}{% endif %}</td>`

### `templates/projects/final_review.html`
- جدول «سایر ردیف‌ها» (متغیر `l`):
  قدیم: `<td class="text-center font-technical">{{ l.qty|floatformat:"-4"|fa_digits }}</td>`
  جدید: `<td class="text-center"><span class="font-technical">{{ l.qty|floatformat:"-4"|fa_digits }}</span>{% if l.unit %} {{ l.get_unit_display }}{% endif %}</td>`
- در آکاردئون خدمت: قدیم `{% if s.line.service.unit %} {{ s.line.service.get_unit_display }}{% endif %}` ← جدید `{% if s.line.unit_label %} {{ s.line.unit_label }}{% endif %}`

### `templates/projects/partials/stage_install.html`
قدیم: `{% if r.line.service.unit %} {{ r.line.service.get_unit_display }}{% endif %}`
جدید: `{% if r.line.unit_label %} {{ r.line.unit_label }}{% endif %}`

### سایر جاها
هر جای دیگری که در خروجی `grep` گام ۰ ردیف **فاکتور یا پیش‌فاکتور** را چاپ می‌کند و بالا نیامده، همین الگو (`{% if x.unit %} {{ x.get_unit_display }}{% endif %}` برای `InvoiceLine`، یا `unit_label` برای `ProjectService/ProjectExtraLine`) را اعمال کن و نامش را در گزارش بیاور.

## گام ۸: `README.md`

در بخش «پیش‌فاکتور و پرداخت» یک مورد اضافه کن:
```
- **واحد هر ردیف:** هر ردیف خدمت واحد خودش را دارد (متر، متر مربع، عدد و ...). با انتخاب خدمت واحد پیش‌فرضش می‌آید و حسابدار هر ردیف را جدا عوض می‌کند؛ بدون واحد ذخیره نمی‌شود. هنگام صدور واحد در `InvoiceLine.unit` کپی می‌شود و کنار مقدار در PDF، پرتال و پرونده‌ی مالی دیده می‌شود. ردیف «اضافه یا تخفیف» هم واحد دارد ولی خالی‌ماندنش مجاز است.
```
`DESIGN_SYSTEM.md` را تغییر نده.

## قواعد این بریف
- تست جدید ننویس و mutation نخواه.
- تست‌های موجود نباید بشکنند. تست قدیمی که ردیف خدمت را بدون واحد ذخیره می‌کند (و خدمتش واحد پیش‌فرض ندارد) به‌خاطر اجباری‌شدن واحد می‌شکند. نامش و علتش را گزارش کن و فقط با **بازنویسی** (دادن `unit` به ردیف یا خدمت) درستش کن. تعداد کل تست‌ها کم نشود.
- متن UI بدون کلمات ممنوع (متن‌ها در بریف داده شده؛ عیناً بگذار).

## گزارش

۱. تعداد تست قبل و بعد و نام تست‌های بازنویسی‌شده، روی sqlite و با `TEST_ON_POSTGRES=True`.
۲. خروجی `makemigrations --check --dry-run` («No changes») و نام دو فایل مایگریشن.
۳. `pnpm run build` بدون خطا.
۴. `grep -rn "innerHTML\|اختیاری\|فعلاً" static/js/proforma_page.js static/js/line_editor.js templates/projects/partials/proforma_body.html` خالی باشد.
۵. فهرست فایل‌ها، فهرست `grep` ردیف‌های فاکتور و جاهای اضافه‌شده، انحراف‌ها، `git log --oneline -3`، `git branch -a`.
۶. یادآوری: گزارش جایگزین تست دستی نیست.

## تست دستی کاربر (لوکال)

۱. در «پیش‌فاکتور و پرداخت» ردیف خدمت جدید بزن. با انتخاب خدمتی که واحد پیش‌فرض دارد، واحد خودکار پر شود. واحد را به «متر مربع» عوض کن و ثبت کن.
۲. خدمتی را انتخاب کن که واحد پیش‌فرض ندارد و واحد را روی «انتخاب واحد» بگذار. باید پیام «واحد «…» را انتخاب کنید.» بیاید.
۳. ردیف موجود را با مداد باز کن و واحدش را عوض کن. مودال باید یک سطر «واحد: متر ← عدد» نشان بدهد.
۴. در جدول صفحه، واحد کنار مقدار دیده شود. ردیف «اضافه یا تخفیف» را با و بدون واحد بزن.
۵. «پیش‌نمایش پیش‌فاکتور مشتری» را بزن و ستون «واحد» را ببین. صادر کن. صفحه‌ی فاکتور مشتری، PDF، پرونده‌ی مالی و بازبینی نهایی واحد را نشان بدهند.
۶. ردیف را عوض کن و بعد از بازتولید فاکتور، واحد هنوز روی ردیف باشد.
۷. روشن/تاریک و موبایل را روی ویرایشگر ردیف و PDF ببین.

## نکته‌ی عملیاتی برای فاکتوری که کارفرما همین الان فرستاد

آن فاکتور قبل از این تغییر ساخته شده و ردیفش واحد ندارد. بعد از deploy حسابدار باید ردیف را با مداد باز کند، واحد درست را انتخاب و ثبت کند. با ثبت، ردیف‌های فاکتور بازتولید می‌شوند و واحد روی PDF می‌آید. قیمت‌ها تغییر نمی‌کنند. اگر مشتری قبلاً تایید یا پرداخت کرده باشد، قیمت‌ها قفل‌اند و این راه بسته است. در آن حالت به من بگو تا برای همان ردیف راه جداگانه بدهیم.

## پرسش‌های غیرمسدود
- فهرست واحدها همین شش واحد کالاست (متر، متر مربع، متر مکعب، لیتر، کیلوگرم، عدد). اگر «شاخه»، «دستگاه» یا «تن» هم لازم دارید، باید به `Item.Unit` اضافه شود.

**موکول‌شده: ندارد.**