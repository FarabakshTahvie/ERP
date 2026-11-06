# بریف ۴ — صفحه‌ی ویرایشگر جدید (شبیه صفحه‌ی مشتری)

> ترتیب اجرا: بعد از merge بریف ۳. شاخه: `feat/proforma-page` (از `main` تازه). بلوک «قواعد ثابت» را خودت اول نشست به دستیار بده؛ اینجا تکرار نشده.
>
> **نکته‌ی این نسخه:** بریف بدون فایل تست تازه و بدون mutation است. در گزارش، بخش mutation و «نام تست‌های جدید» نیاید. اگر تست موجودی به‌خاطر این تغییر شکست (مثلاً تست قدیمی `proforma_editor`)، نام و علتش را گزارش کن و فقط با بازنویسی درستش کن.
>
> **سه نکته درباره‌ی این بریف:**
> - صفحه برای پروژه‌ی قفل‌شده، تکمیل‌شده یا لغوشده دیگر ریدایرکت نمی‌شود. فقط‌خواندنی باز می‌شود، چون بریف ۶ پرداخت و سررسید را به همین صفحه می‌آورد.
> - بعد از صدور، کاربر هنوز به نمای پروژه می‌رود. بریف ۵ این را عوض می‌کند.
> - یک فرم صدور موقت می‌گذاریم تا کار صدور نخوابد؛ بریف ۵ آن را با پیش‌نمایش جایگزین می‌کند.

**شاخه:** `feat/proforma-page`

**توضیح ساده:** جدول ردیف‌ها شبیه فاکتور مشتری است. زیرش دکمه‌ی «+» ردیف تازه را همان‌جا باز می‌کند. هر ردیف مداد و سطل دارد. ثبت ردیف تازه فوری ذخیره می‌شود. ویرایش یا حذف اول مودالی نشان می‌دهد که «چه به چه» عوض می‌شود. بعد از ذخیره صفحه رفرش نمی‌شود و فقط بخش جدول با htmx دوباره آورده می‌شود (HTML از قالب Django می‌آید، نه از متن خام).

**فایل‌ها:** `static/js/line_editor.js` (چهار تغییر کوچک)، `static/js/proforma_page.js` (تازه)، `static/src/input.css`، `projects/views.py`، `projects/urls.py`، `utils/navigation.py`، `templates/projects/proforma_editor.html` (بازنویسی)، `templates/projects/partials/proforma_body.html` (تازه)، حذف `templates/projects/partials/proforma_fees.html`.

### گام ۰
```
git log --oneline -5 && ls projects/proforma_rows.py static/js/line_editor.js
grep -rn "proforma_fees\|_proforma_initial_rows\|_proforma_extra_rows" --include=*.py --include=*.html . | grep -v tests
grep -rn "proforma_editor" --include=*.py . | grep tests
```
خروجی گرپ را در گزارش بیاور.

### گام ۱ — `static/js/line_editor.js` (چهار جایگزینی)
۱. قدیم: `      cellsEl.appendChild(rm);` ← جدید: `      if (!ctx.noRemove) cellsEl.appendChild(rm);`
۲. قدیم: `    root.appendChild(rowsBox); root.appendChild(empty); root.appendChild(add);` ← جدید:
```js
    root.appendChild(rowsBox);
    if (!cfg.single) { root.appendChild(empty); root.appendChild(add); }
```
۳. قدیم: `    top = makeLevel(cfg, rowsBox, notify, { sprite: sprite, nested: false });` ← جدید: `    top = makeLevel(cfg, rowsBox, notify, { sprite: sprite, nested: false, noRemove: !!cfg.single });`
۴. قدیم:
```js
    (cfg.initial || []).forEach(function (r) { top.addRow(r); });
    loading = false;
```
جدید:
```js
    (cfg.initial || []).forEach(function (r) { top.addRow(r); });
    if (cfg.single && !top.rows.length) top.addRow();
    loading = false;
```
`single: true` یعنی ویرایشگرِ فقط یک ردیف، بدون دکمه‌ی افزودن و حذف ردیف اصلی.

### گام ۲ — `static/src/input.css`
بعد از خط `@source "../js/purchase_lines.js";` اضافه کن: `@source "../js/proforma_page.js";`

### گام ۳ — `static/js/proforma_page.js` (تازه، عیناً)
```js
(function () {
  var dlg = document.getElementById('pf-confirm');
  if (!dlg) return;
  var session = null;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function data(id) {
    var n = document.getElementById(id);
    try { return JSON.parse((n && n.textContent) || '[]'); } catch (e) { return []; }
  }
  function root() { return document.getElementById('pf-body'); }
  function form(obj) {
    var fd = new FormData();
    Object.keys(obj).forEach(function (k) { fd.append(k, obj[k]); });
    return fd;
  }
  function post(url, obj) { return window.fbSend(url, form(obj), window.FB_CSRF); }
  function refresh() {
    var r = root();
    if (window.htmx && r) { window.htmx.ajax('GET', r.dataset.fragmentUrl, { target: '#pf-body', swap: 'outerHTML' }); return; }
    window.location.reload();
  }
  function say(node, text) { node.textContent = text || ''; node.classList.toggle('hidden', !text); }

  // ---------- مشخصات ویرایشگر ----------
  function serviceSpec(box, hidden, initial) {
    var E = window.fbLineEditor, num = E.num, fmt = E.fmt;
    var qtyFmt = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 4 });
    var items = data('items-data'), byId = {};
    items.forEach(function (i) { byId[i.id] = i; });
    function item(d) { return byId[parseInt(d.item_id, 10)]; }
    function matAuto(d) { var it = item(d); return it ? Math.round(num(d.qty) * parseFloat(it.cost) * (100 + parseFloat(it.margin)) / 100) : 0; }
    function matTotal(d) { var t = String(d.line_total == null ? '' : d.line_total).trim(); return t !== '' ? num(t) : matAuto(d); }
    function svcTotal(d) {
      var t = num(d.qty) * num(d.unit_price);
      (d.materials || []).forEach(function (m) { t += matTotal(m); });
      return Math.round(t);
    }
    function stockNote(d) {
      var it = item(d);
      if (!it) return '';
      var stock = parseFloat(it.stock), qty = num(d.qty);
      if (stock <= 0 && !(parseFloat(it.cost) > 0)) return { tone: 'warning', text: 'موجودی انبار صفر است و میانگینی هم ندارد؛ جمع این کالا را خودتان بنویسید.' };
      if (stock <= 0) return { tone: 'warning', text: 'موجودی انبار صفر است؛ میانگین مال آخرین خریدهاست و ممکن است قدیمی باشد.' };
      if (qty > stock) return { tone: 'warning', text: 'موجودی انبار ' + qtyFmt.format(stock) + ' ' + it.unit + ' است؛ ' + qtyFmt.format(qty - stock) + ' ' + it.unit + ' کم دارید.' };
      return 'موجودی انبار: ' + qtyFmt.format(stock) + ' ' + it.unit;
    }
    return {
      single: true, mount: box, hidden: hidden, initial: initial ? [initial] : [],
      columns: [
        { key: 'service_id', type: 'picker', label: 'خدمت', items: data('services-data'), placeholder: 'جستجوی خدمت...', cls: 'flex-1 min-w-48' },
        { key: 'qty', type: 'number', label: 'مقدار', cls: 'w-24' },
        { key: 'unit_price', type: 'money', label: 'قیمت خود خدمت (تومان، هر واحد)', cls: 'w-44' }
      ],
      children: {
        key: 'materials', title: 'متریال / قطعات / مصرفی این خدمت', addLabel: 'افزودن کالا',
        columns: [
          { key: 'item_id', type: 'picker', label: 'کالا', items: items, placeholder: 'جستجوی کالا...', cls: 'flex-1 min-w-48' },
          { key: 'qty', type: 'number', label: 'مقدار', cls: 'w-24' },
          { key: 'cost', type: 'readonly', label: 'میانگین', cls: 'w-28',
            compute: function (d) { var it = item(d); return !it ? '—' : (parseFloat(it.cost) > 0 ? fmt(parseFloat(it.cost)) : 'بدون بها!'); } },
          { key: 'margin', type: 'readonly', label: 'سود ٪', cls: 'w-16',
            compute: function (d) { var it = item(d); return it ? fmt(parseFloat(it.margin)) : '—'; } },
          { key: 'line_total', type: 'money', label: 'جمع (تومان)', cls: 'w-36', center: true,
            auto: function (d) { return item(d) && num(d.qty) > 0 ? String(matAuto(d)) : ''; } }
        ],
        footer: stockNote
      },
      footer: function (d) { return 'جمع این خدمت (برآوردی): ' + fmt(svcTotal(d)) + ' تومان'; }
    };
  }
  function extraSpec(box, hidden, initial) {
    return {
      single: true, mount: box, hidden: hidden, initial: initial ? [initial] : [],
      columns: [
        { key: 'title', type: 'text', label: 'شرح', cls: 'flex-1 min-w-48' },
        { key: 'kind', type: 'select', label: 'نوع', cls: 'w-36', options: [['extra', 'هزینه‌ی اضافه'], ['discount', 'تخفیف']] },
        { key: 'qty', type: 'number', label: 'مقدار', cls: 'w-24' },
        { key: 'unit_price', type: 'money', label: 'مبلغ واحد (تومان)', cls: 'w-40' }
      ]
    };
  }

  // ---------- جلسه‌ی ویرایش ----------
  function closeSession() { if (session) { session.cleanup(); session = null; } }

  function buildSession(kind, mount, cleanup) {
    var err = el('p', 'fb-error hidden');
    var actions = el('div', 'flex gap-2 pt-2');
    var ok = el('button', 'btn btn-primary btn-sm', 'ثبت'); ok.type = 'button';
    var cancel = el('button', 'btn btn-ghost btn-sm', 'انصراف'); cancel.type = 'button';
    cancel.addEventListener('click', closeSession);
    ok.addEventListener('click', submit);
    actions.appendChild(ok); actions.appendChild(cancel);
    mount.appendChild(err); mount.appendChild(actions);
    return { kind: kind, err: err, ok: ok, cleanup: cleanup };
  }

  function openRowEditor(kind, mount, initial, viewRow, editRow) {
    closeSession();
    mount.textContent = '';
    var box = el('div'), hidden = el('input');
    hidden.type = 'hidden';
    box.dataset.sprite = root().dataset.sprite || '';
    mount.appendChild(box); mount.appendChild(hidden);
    window.fbLineEditor(kind === 'service' ? serviceSpec(box, hidden, initial) : extraSpec(box, hidden, initial));
    session = buildSession(kind, mount, function () {
      mount.textContent = '';
      if (viewRow) { viewRow.classList.remove('hidden'); editRow.classList.add('hidden'); } else mount.classList.add('hidden');
    });
    session.hidden = hidden;
    session.pk = initial ? initial.pk : '';
    if (viewRow) { viewRow.classList.add('hidden'); editRow.classList.remove('hidden'); } else mount.classList.remove('hidden');
  }

  function openFeeEditor(row) {
    closeSession();
    var cell = row.querySelector('[data-fee-value]'), text = cell.querySelector('[data-fee-text]');
    var field = row.dataset.field, box = el('div', 'flex flex-col gap-2');
    var input = el('input', 'input input-xs w-40 font-technical');
    input.type = 'text'; input.dir = 'ltr'; input.autocomplete = 'off';
    if (field === 'contract_date') {
      input.setAttribute('data-jalali-date', ''); input.setAttribute('data-clearable', ''); input.setAttribute('inputmode', 'none');
    } else {
      input.setAttribute('data-money', ''); input.setAttribute('inputmode', 'numeric'); input.setAttribute('maxlength', '12');
    }
    input.value = row.dataset.raw || '';
    if (window.fbMoney && field !== 'contract_date') window.fbMoney.format(input);
    box.appendChild(input);
    text.classList.add('hidden');
    cell.appendChild(box);
    session = buildSession('fee', box, function () { box.remove(); text.classList.remove('hidden'); });
    session.field = field; session.input = input;
    input.focus();
  }

  // ---------- مودال تایید ----------
  function showConfirm(res, title, onOk) {
    dlg.querySelector('[data-pf-title]').textContent = title;
    var list = dlg.querySelector('[data-pf-changes]');
    list.textContent = '';
    res.changes.forEach(function (c) {
      var row = el('div', 'fb-inset flex flex-col gap-1 text-xs');
      row.appendChild(el('span', 'font-semibold', c.label));
      var line = el('div', 'flex items-center gap-2 flex-wrap');
      line.appendChild(el('span', 'fb-muted font-technical', c.old));
      line.appendChild(el('span', null, '←'));
      line.appendChild(el('span', 'font-technical font-semibold', c['new']));
      row.appendChild(line);
      list.appendChild(row);
    });
    dlg.querySelector('[data-pf-grand]').textContent = res.grand_before + ' ← ' + res.grand_after + ' تومان';
    say(dlg.querySelector('[data-pf-error]'), '');
    dlg._ok = onOk;
    dlg.showModal();
  }
  function afterSave(res) {
    if (!res.ok) { say(dlg.querySelector('[data-pf-error]'), res.error || 'ثبت نشد.'); return; }
    if (dlg.open) dlg.close();
    closeSession();
    refresh();
  }

  // ---------- ثبت ----------
  function args() {
    if (session.kind === 'fee') return { kind: 'fee', field: session.field, value: session.input.value };
    return { kind: session.kind, row_json: session.hidden.value };
  }
  function submit() {
    var a = args(), r = root();
    if (a.row_json === '[]') { say(session.err, 'ردیف را کامل کنید.'); return; }
    say(session.err, '');
    session.ok.disabled = true;
    post(r.dataset.previewUrl, a).then(function (res) {
      if (!session) return;
      session.ok.disabled = false;
      if (!res.ok) { say(session.err, res.error || 'بررسی نشد.'); return; }
      if (res.same) { closeSession(); return; }
      var send = function () { return post(r.dataset.saveUrl, a).then(afterSave); };
      if (res.is_new) { send(); return; }
      showConfirm(res, 'تایید تغییر', send);
    });
  }
  function askDelete(row) {
    var r = root(), a = { kind: row.dataset.kind, pk: row.dataset.pk };
    post(r.dataset.previewUrl, { kind: a.kind, op: 'delete', pk: a.pk }).then(function (res) {
      if (!res.ok) { window.alert(res.error || 'بررسی نشد.'); return; }
      showConfirm(res, 'حذف ردیف', function () { return post(r.dataset.deleteUrl, a).then(afterSave); });
    });
  }

  dlg.querySelector('[data-pf-ok]').addEventListener('click', function () { if (dlg._ok) dlg._ok(); });
  dlg.querySelector('[data-pf-cancel]').addEventListener('click', function () { dlg.close(); });

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-add],[data-edit],[data-delete],[data-fee-edit]') : null;
    if (!t || !t.closest('#pf-body')) return;
    var row = t.closest('[data-row]') || t.closest('[data-fee-row]');
    if (t.hasAttribute('data-add')) openRowEditor(t.dataset.add, root().querySelector('[data-add-mount]'), null, null, null);
    else if (t.hasAttribute('data-edit')) openRowEditor(row.dataset.kind, row.nextElementSibling.querySelector('[data-editor-mount]'), JSON.parse(row.dataset.json), row, row.nextElementSibling);
    else if (t.hasAttribute('data-delete')) askDelete(row);
    else if (t.hasAttribute('data-fee-edit')) openFeeEditor(row);
  });
})();
```

### گام ۴ — ویو (`projects/views.py`)
۱. importها: `from .services import resolve_billing_party` را به فهرست `from .services import (...)` اضافه کن و `from .proforma_rows import proforma_summary` بگذار. از فهرست `from .proforma import (...)` فقط `issue_proforma, proforma_stage, can_issue_proforma` را نگه دار (`parse_service_rows, parse_extra_rows, save_proforma` را بردار). اگر نامی که در کد پایین به کار رفته (مثل `_line_choices`، `stock_map`، `has_global_margin`، `resolve_margin_percents`، `project_prices_editable`، `EDITABLE_PROJECT_STATUSES`) در فایل import نشده بود، توقف و گزارش؛ اسمی از خودت نساز.

۲. از `def _proforma_extra_rows(project):` تا آخر فایل (دو تابع کمکی و `proforma_editor` قدیمی) را پاک کن و این را بگذار:

```python
def _stale_items(project):
    """کالاهایی که میانگین یا سودشان بعد از آخرین ثبت ردیف عوض شده (جمع دستی‌نوشته نباشد)."""
    mats = [m for l in project.services.prefetch_related("materials__item") for m in l.materials.all()]
    if not mats:
        return []
    now_margin = resolve_margin_percents({m.item for m in mats})
    return sorted({
        m.item.name for m in mats
        if not m.manual_total and (
            m.cost_snapshot != m.item.moving_average_cost
            or m.margin_percent != Decimal(now_margin[m.item_id]).quantize(Decimal("0.01")))
    })


def _proforma_context(request, project):
    invoice = getattr(project, "invoice", None)
    prices_open = project_prices_editable(project)
    editable = prices_open and project.status in EDITABLE_PROJECT_STATUSES
    stage = proforma_stage(project)
    can_issue = bool(editable and invoice is None and stage
                     and stage.status == ProjectStage.Status.IN_PROGRESS
                     and can_issue_proforma(request.user, stage))
    services, items = _line_choices(project)
    margins = resolve_margin_percents(items)
    stock = stock_map(i.pk for i in items)
    return {
        "project": project, "invoice": invoice, "stage": stage,
        "billing_party": resolve_billing_party(project),
        "editable": editable, "prices_open": prices_open, "can_issue": can_issue,
        "summary": proforma_summary(project),
        "services_data": [{"id": s.id, "name": s.name, "unit": s.get_unit_display() if s.unit else ""}
                          for s in services],
        "items_data": [{"id": i.id, "name": i.name, "unit": i.get_unit_display(),
                        "cost": str(i.moving_average_cost), "margin": str(margins[i.pk]),
                        "stock": str(stock.get(i.pk, Decimal("0")))} for i in items],
        "has_global_margin": has_global_margin(),
        "stale_items": _stale_items(project) if editable else [],
    }


@login_required
def proforma_editor(request, project_id):
    project = get_object_or_404(Project.objects.select_related("location", "partner", "owner"), pk=project_id)
    if not can_edit_pricing(request.user, project):
        raise Http404
    if request.method == "POST":   # ردیف‌ها دیگر با فرم نمی‌آیند (مسیرهای row_save/row_delete)؛ فقط صدور
        if request.POST.get("action") == "issue":
            try:
                invoice, conflict = issue_proforma(
                    project=project, actor=request.user, send_sms=request.POST.get("send_sms") == "on",
                    deadline_days=request.POST.get("deadline_days"))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("projects:proforma_editor", project.id)
            messages.success(request, f"پیش‌فاکتور {invoice.number} صادر شد.")
            if conflict:
                messages.warning(request, "این شماره موبایل قبلاً برای یک حساب دیگر (مثلاً پرسنل) ثبت شده؛ حساب ورود خودکار ساخته نشد. از پنل ادمین دستی حساب بسازید.")
            return redirect("projects:staff_project_overview", project.id)
        return redirect("projects:proforma_editor", project.id)
    return render(request, "projects/proforma_editor.html", _proforma_context(request, project))


@login_required
def proforma_body(request, project_id):
    """فقط بخش جدول؛ بعد از هر ذخیره‌ی ردیف با htmx جایگزین می‌شود (صفحه رفرش نمی‌شود)."""
    project = get_object_or_404(Project, pk=project_id)
    if not can_edit_pricing(request.user, project):
        raise Http404
    return render(request, "projects/partials/proforma_body.html", _proforma_context(request, project))
```

۳. بعد از این تغییر `grep -n "_cost_values" projects/views.py`. اگر جز تعریفش جای دیگری نبود، تابع را پاک کن.

### گام ۵ — URL و ناوبری
در `projects/urls.py` بعد از سه مسیر `proforma_row_*`:
```python
    path("staff/projects/<int:project_id>/proforma/body/", views.proforma_body, name="proforma_body"),
```
در `utils/navigation.py` به `NON_PAGE` اضافه کن: `"projects:proforma_body",`

### گام ۶ — تمپلیت‌ها

**۱. `templates/projects/partials/proforma_fees.html` را پاک کن.** گام ۰ نشان می‌دهد جای دیگری include نشده. بعدش grep بزن و خروجی را بیاور.

**۲. `templates/projects/partials/proforma_body.html` (تازه):**
```html
{% load static custom_tags %}
<div id="pf-body" class="flex flex-col gap-5"
     data-fragment-url="{% url 'projects:proforma_body' project.id %}"
     data-preview-url="{% url 'projects:proforma_row_preview' project.id %}"
     data-save-url="{% url 'projects:proforma_row_save' project.id %}"
     data-delete-url="{% url 'projects:proforma_row_delete' project.id %}"
     data-sprite="{% static 'icons/sprite.svg' %}">

    {% if not editable %}
    <div role="alert" class="alert alert-soft alert-warning">
        {% icon "lock" "w-4 h-4 shrink-0" %}
        <span class="text-xs">ویرایش قیمت‌ها بسته است؛ پیش‌فاکتور تایید شده، پرداختی ثبت شده، یا پروژه تکمیل یا لغو شده است.</span>
    </div>
    {% else %}
    {% if not has_global_margin %}
    <div role="alert" class="alert alert-soft alert-warning">
        {% icon "alert-triangle" "w-4 h-4 shrink-0" %}
        <span class="text-xs">قانون سود عمومی (درصدی) تعریف نشده؛ سود همه‌ی کالاها صفر حساب می‌شود. از پنل مدیریت ← «قوانین سود» یک قانون سراسری بسازید.</span>
    </div>
    {% endif %}
    {% if stale_items %}
    <div role="alert" class="alert alert-soft alert-warning">
        {% icon "alert-triangle" "w-4 h-4 shrink-0" %}
        <span class="text-xs">قیمت یا سود این کالاها بعد از آخرین ثبت تغییر کرده: {{ stale_items|join:"، " }}. برای به‌روزشدن، ردیف مربوط را با مداد باز کنید و دوباره ثبت کنید؛ مودال تفاوت را نشان می‌دهد. تا آن موقع پیش‌فاکتور با همان عدد قبلی می‌ماند.</span>
    </div>
    {% endif %}
    {% endif %}

    <section class="fb-card fb-pad flex flex-col gap-5">
        <div class="flex items-start justify-between gap-4 flex-wrap pb-5 border-b border-base-300">
            <img src="{% static 'icons/logo-invoice.svg' %}" alt="فرابخش تهویه"
                 class="h-12 bg-white rounded-field p-1.5 border border-base-300">
            <div class="text-xs flex flex-col gap-1">
                <div><span class="fb-muted">طرف‌حساب:</span> <span class="font-semibold">{{ billing_party.name }}</span></div>
                <div><span class="fb-muted">پروژه:</span> <span class="font-semibold">{{ project.name }}</span></div>
                <div class="flex items-center gap-1">
                    <span class="fb-muted">وضعیت:</span>
                    {% if invoice %}
                    <span class="fb-badge fb-badge-neutral">{{ invoice.get_status_display }}</span>
                    <span class="font-technical">{{ invoice.number|fa_digits }}</span>
                    {% else %}
                    <span class="fb-badge fb-badge-warning">هنوز صادر نشده</span>
                    {% endif %}
                </div>
            </div>
        </div>

        <p class="fb-hint">مشتری فقط جمع هر خدمت را می‌بیند؛ کالاهای زیر هر خدمت فقط برای شماست. هر تغییر روی ردیف‌های موجود قبل از ذخیره، «چه به چه» را در مودال نشان می‌دهد.</p>

        <div class="overflow-x-auto">
            <table class="table table-sm">
                <thead>
                    <tr class="text-xs fb-muted">
                        <th class="w-12 text-center font-medium">ردیف</th>
                        <th class="font-medium">شرح</th>
                        <th class="text-center font-medium">مقدار</th>
                        <th class="text-center font-medium">مبلغ واحد (تومان)</th>
                        <th class="text-center font-medium">جمع (تومان)</th>
                        {% if editable %}<th class="w-24"><span class="sr-only">عملیات</span></th>{% endif %}
                    </tr>
                </thead>
                <tbody>
                    {% for s in summary.services %}
                    <tr data-row data-kind="service" data-pk="{{ s.line.pk }}" data-json="{{ s.json }}">
                        <td class="text-center font-technical">{{ forloop.counter|fa_digits }}</td>
                        <td>
                            <div class="font-medium">{{ s.line.service.name }}</div>
                            {% for m in s.materials %}
                            <div class="text-xs fb-muted">{{ m.item.name }} — <span class="font-technical">{{ m.qty|floatformat:"-4"|fa_digits }}</span> {{ m.item.get_unit_display }} — <span class="font-technical">{{ m.line_total|intcomma_fa }}</span></div>
                            {% endfor %}
                        </td>
                        <td class="text-center font-technical">{{ s.line.qty|floatformat:"-2"|fa_digits }}</td>
                        <td class="text-center font-technical">{{ s.line.unit_price|intcomma_fa }}</td>
                        <td class="text-center font-technical font-semibold">{{ s.total|intcomma_fa }}</td>
                        {% if editable %}
                        <td>
                            <div class="flex items-center justify-end gap-1">
                                <button type="button" class="btn btn-ghost btn-xs btn-square" data-edit aria-label="ویرایش ردیف">{% icon "pencil" "w-4 h-4" %}</button>
                                <button type="button" class="btn btn-soft btn-error btn-xs btn-square" data-delete aria-label="حذف ردیف">{% icon "trash-2" "w-4 h-4" %}</button>
                            </div>
                        </td>
                        {% endif %}
                    </tr>
                    {% if editable %}<tr class="hidden"><td colspan="6"><div data-editor-mount class="fb-inset"></div></td></tr>{% endif %}
                    {% endfor %}

                    {% with base=summary.services|length %}
                    {% for x in summary.extras %}
                    <tr data-row data-kind="extra" data-pk="{{ x.line.pk }}" data-json="{{ x.json }}">
                        <td class="text-center font-technical">{{ forloop.counter|add:base|fa_digits }}</td>
                        <td>
                            <span class="font-medium">{{ x.line.title }}</span>
                            <span class="fb-badge {% if x.line.kind == 'discount' %}fb-badge-success{% else %}fb-badge-warning{% endif %}">{{ x.line.get_kind_display }}</span>
                        </td>
                        <td class="text-center font-technical">{{ x.line.qty|floatformat:"-2"|fa_digits }}</td>
                        <td class="text-center font-technical">{{ x.line.unit_price|intcomma_fa }}</td>
                        <td class="text-center font-technical font-semibold">{{ x.total|intcomma_fa }}</td>
                        {% if editable %}
                        <td>
                            <div class="flex items-center justify-end gap-1">
                                <button type="button" class="btn btn-ghost btn-xs btn-square" data-edit aria-label="ویرایش ردیف">{% icon "pencil" "w-4 h-4" %}</button>
                                <button type="button" class="btn btn-soft btn-error btn-xs btn-square" data-delete aria-label="حذف ردیف">{% icon "trash-2" "w-4 h-4" %}</button>
                            </div>
                        </td>
                        {% endif %}
                    </tr>
                    {% if editable %}<tr class="hidden"><td colspan="6"><div data-editor-mount class="fb-inset"></div></td></tr>{% endif %}
                    {% endfor %}
                    {% endwith %}

                    {% if not summary.services and not summary.extras %}
                    <tr><td colspan="6" class="fb-empty">هنوز ردیفی ثبت نشده است.</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>

        {% if editable %}
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button type="button" class="btn btn-dash btn-primary btn-sm w-full" data-add="service">{% icon "plus" "w-4 h-4" %} افزودن خدمت</button>
            <button type="button" class="btn btn-dash btn-sm w-full" data-add="extra">{% icon "plus" "w-4 h-4" %} ردیف اضافه یا تخفیف</button>
        </div>
        <div class="hidden fb-inset" data-add-mount></div>
        {% endif %}

        <div class="flex flex-col">
            {% for f in summary.fees %}
            <div class="flex items-center justify-between gap-2 flex-wrap py-2 border-t border-base-300" data-fee-row data-field="{{ f.field }}" data-raw="{{ f.raw }}">
                <span class="text-sm">{{ f.label }}</span>
                <div class="flex items-center gap-2">
                    <div data-fee-value class="flex items-center gap-2 flex-wrap">
                        <span data-fee-text class="font-technical text-sm">{% if f.value %}{{ f.value|intcomma_fa }} تومان{% else %}—{% endif %}</span>
                    </div>
                    {% if editable %}<button type="button" class="btn btn-ghost btn-xs btn-square" data-fee-edit aria-label="ویرایش {{ f.label }}">{% icon "pencil" "w-4 h-4" %}</button>{% endif %}
                </div>
            </div>
            {% endfor %}
            <div class="flex items-center justify-between gap-2 flex-wrap py-2 border-t border-base-300" data-fee-row data-field="contract_date" data-raw="{{ summary.contract_raw }}">
                <span class="text-sm">تاریخ قرارداد</span>
                <div class="flex items-center gap-2">
                    <div data-fee-value class="flex items-center gap-2 flex-wrap">
                        <span data-fee-text class="font-technical text-sm">{% if summary.contract_date %}{{ summary.contract_date|to_jalali:"%Y/%m/%d" }}{% else %}—{% endif %}</span>
                    </div>
                    {% if editable %}<button type="button" class="btn btn-ghost btn-xs btn-square" data-fee-edit aria-label="ویرایش تاریخ قرارداد">{% icon "pencil" "w-4 h-4" %}</button>{% endif %}
                </div>
            </div>
            {% if summary.participants_cost %}
            <div class="flex items-center justify-between gap-2 flex-wrap py-2 border-t border-base-300">
                <span class="text-sm">هزینه‌ی عوامل اجرایی بیرونی</span>
                <span class="font-technical text-sm">{{ summary.participants_cost|intcomma_fa }} تومان</span>
            </div>
            {% endif %}
        </div>

        <div class="flex justify-end">
            <div class="w-full md:w-80 flex flex-col gap-2 text-sm">
                <div class="flex justify-between gap-2 font-bold">
                    <span>جمع پیش‌فاکتور</span>
                    <span><span class="font-technical" data-grand>{{ summary.grand_total|intcomma_fa }}</span> تومان</span>
                </div>
                {% if invoice %}
                <div class="flex justify-between gap-2 text-success">
                    <span>پرداخت‌شده</span><span><span class="font-technical">{{ invoice.paid_amount|intcomma_fa }}</span> تومان</span>
                </div>
                <div class="flex justify-between gap-2 border-t border-base-300 pt-2">
                    <span>مانده</span><span><span class="font-technical">{{ invoice.remaining_amount|intcomma_fa }}</span> تومان</span>
                </div>
                {% endif %}
            </div>
        </div>
    </section>

    {% if can_issue %}
    <form method="post" data-fb-once class="fb-card fb-pad flex flex-col gap-3">
        {% csrf_token %}
        <input type="hidden" name="action" value="issue">
        <h2 class="fb-section-title">صدور پیش‌فاکتور</h2>
        <div class="fb-field max-w-xs">
            <label class="fb-label" for="pf-deadline">مهلت تایید مشتری (روز)</label>
            <input type="text" id="pf-deadline" name="deadline_days" value="1" data-digits maxlength="2" dir="ltr" inputmode="numeric" autocomplete="off" class="input w-full font-technical">
            <span class="fb-hint">مشتری تا ساعت ۲۴ روز آخر مهلت دارد؛ مثلاً امروز با مهلت ۱ روز یعنی تا ساعت ۲۴ فردا.</span>
        </div>
        <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" name="send_sms" class="checkbox checkbox-sm" checked>
            <span class="text-sm">پیامک پیش‌فاکتور همراه با نام کاربری و رمز عبور برای طرف‌حساب ارسال شود</span>
        </label>
        <button type="submit" class="btn btn-primary btn-sm self-start">صدور پیش‌فاکتور</button>
    </form>
    {% endif %}

    {% if editable %}
    {{ services_data|json_script:"services-data" }}
    {{ items_data|json_script:"items-data" }}
    {% endif %}
</div>
```

**۳. `templates/projects/proforma_editor.html` را کامل با این بازنویسی کن:**
```html
{% extends "base.html" %}
{% load static custom_tags %}
{% block title %}پیش‌فاکتور | فرابخش{% endblock %}
{% block content %}
<div class="fb-page fb-page--lg">
    <div>
        <a href="{% nav_url 'projects:staff_project_overview' project.id %}" class="link link-hover text-sm fb-muted">بازگشت به پروژه</a>
        <h1 class="fb-page-title mt-2">پیش‌فاکتور</h1>
        <p class="fb-page-sub">{{ project.name }} — <span class="font-technical">{{ project.code|fa_digits }}</span></p>
    </div>
    {% include "projects/partials/proforma_body.html" %}
</div>

<dialog id="pf-confirm" class="modal">
    <div class="modal-box max-w-md flex flex-col gap-3">
        <h3 class="font-bold text-base" data-pf-title></h3>
        <p class="text-xs fb-muted">تغییرها را بخوانید. بعد از تایید همین لحظه ذخیره می‌شود و روی پیش‌فاکتور اثر می‌گذارد.</p>
        <div class="flex flex-col gap-2 max-h-[50vh] overflow-y-auto" data-pf-changes></div>
        <div class="fb-inset flex items-center justify-between gap-2 text-sm">
            <span class="fb-muted">جمع پیش‌فاکتور (تومان)</span>
            <span class="font-technical font-semibold" data-pf-grand></span>
        </div>
        <p class="fb-error hidden" data-pf-error></p>
        <div class="modal-action">
            <button type="button" class="btn btn-ghost btn-sm" data-pf-cancel>انصراف</button>
            <button type="button" class="btn btn-primary btn-sm" data-pf-ok>تایید و ذخیره</button>
        </div>
    </div>
    <form method="dialog" class="modal-backdrop"><button>close</button></form>
</dialog>
{% endblock %}

{% block extra_js %}
<script src="{% static_v 'js/uploader.js' %}"></script>
<script src="{% static_v 'js/item_picker.js' %}"></script>
<script src="{% static_v 'js/line_editor.js' %}"></script>
<script src="{% static_v 'js/proforma_page.js' %}"></script>
{% endblock %}
```
`uploader.js` لازم است چون `window.fbSend` را همان تعریف می‌کند و `base.html` آن را بارگذاری نمی‌کند.

### گام ۷ — سه اصلاح روی `static/js/proforma_page.js` (اشکال از کد خود من بود)
۱. ثبت ردیف تازه دوبار کلیک می‌خورد و دو ردیف می‌ساخت؛ خطای ثبت ردیف تازه هم داخل مودالِ بسته نوشته می‌شد.

قدیم:
```js
      session.ok.disabled = false;
      if (!res.ok) { say(session.err, res.error || 'بررسی نشد.'); return; }
      if (res.same) { closeSession(); return; }
      var send = function () { return post(r.dataset.saveUrl, a).then(afterSave); };
      if (res.is_new) { send(); return; }
```
جدید:
```js
      if (!res.ok) { session.ok.disabled = false; say(session.err, res.error || 'بررسی نشد.'); return; }
      if (res.same) { closeSession(); return; }
      var send = function () { return post(r.dataset.saveUrl, a).then(afterSave); };
      if (res.is_new) {
        send().then(function () { if (session) session.ok.disabled = false; });
        return;
      }
      session.ok.disabled = false;
```
۲. قدیم: `  function afterSave(res) {` و خط بعدش `    if (!res.ok) { say(dlg.querySelector('[data-pf-error]'), res.error || 'ثبت نشد.'); return; }`
جدید:
```js
  function afterSave(res) {
    if (!res.ok) {
      if (dlg.open) say(dlg.querySelector('[data-pf-error]'), res.error || 'ثبت نشد.');
      else if (session) say(session.err, res.error || 'ثبت نشد.');
      return;
    }
```
۳. دکمه‌ی «تایید و ذخیره» دوبار کلیک می‌خورد. قدیم:
```js
  dlg.querySelector('[data-pf-ok]').addEventListener('click', function () { if (dlg._ok) dlg._ok(); });
```
جدید:
```js
  var okBtn = dlg.querySelector('[data-pf-ok]');
  okBtn.addEventListener('click', function () {
    if (!dlg._ok || okBtn.disabled) return;
    okBtn.disabled = true;
    Promise.resolve(dlg._ok()).then(function () { okBtn.disabled = false; });
  });
```

### گام ۸ — بررسی (بدون تست تازه)
هیچ فایل تست تازه‌ای ساخته نشود (نه `projects/tests_proforma_page.py`). کل تست‌های موجود را اجرا کن. اگر تست قدیمی `proforma_editor` یا ریدایرکت پروژه‌ی تکمیل‌شده شکست، نام و علتش را گزارش کن و فقط با بازنویسی درستش کن. این‌ها را اجرا کن و خروجی را در گزارش بیاور:
```
python manage.py check
pnpm run build
grep -rn "proforma_fees\|save_proforma\|_proforma_initial_rows\|_proforma_extra_rows\|extras_json\|services_json\|proforma-form" --include=*.py --include=*.html . | grep -v tests
grep -n "innerHTML\|outerHTML\|insertAdjacentHTML\|document.write\|eval(" static/js/proforma_page.js
grep -n "proforma_page.js" static/src/input.css
```
(گرپ اول فقط باید به `save_proforma` داخل `projects/proforma.py` و تست‌های قدیمی برسد؛ در `views.py` و تمپلیت‌ها نباید چیزی بماند. گرپ دوم باید خالی باشد.)

### گزارش
طبق قواعد ثابت، به‌علاوه:
- گواهی `pnpm run build`
- خروجی `grep -rn "proforma_fees\|save_proforma" --include=*.py --include=*.html .`
- فهرست تست‌های قدیمی که بازنویسی شدند

### تست دستی (کاربر)
با `tech_accountant_1` روی پروژه‌ای که بازدیدش تمام شده:
- با «افزودن خدمت» یک ردیف با کالا بساز. بدون رفرش در جدول بیاید و جمع عوض شود.
- ثبت ردیف تازه را با دوبار کلیک سریع امتحان کن؛ فقط یک ردیف ساخته شود.
- با مداد مقدار را عوض کن. مودال «قدیم ← جدید» بیاید. «انصراف» چیزی ذخیره نکند.
- ردیف را حذف کن، یک تخفیف اضافه کن، هزینه‌ی نصب و تاریخ قرارداد را عوض کن.
- با کاربری که دسترسی ویرایش قیمت ندارد، آدرس صفحه و آدرس `.../proforma/body/` ۴۰۴ بدهد.
- روشن و تاریک و موبایل را ببین.
- بعد از صدور، همین صفحه فقط‌خواندنی شود.

**پرسش غیرمسدودکننده:** برای ردیف تازه مودال تایید نمی‌آید (طبق خواسته‌ات). برای «افزودن» هم مودال بیاید؟
**موکول:** پیش‌نمایش صدور (بریف ۵)، انتقال پرداخت و سررسید (۶)، لینک‌ها و پاک‌سازی (۷).
