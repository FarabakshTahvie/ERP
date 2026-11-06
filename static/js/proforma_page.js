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
    if (!res.ok) {
      if (dlg.open) say(dlg.querySelector('[data-pf-error]'), res.error || 'ثبت نشد.');
      else if (session) say(session.err, res.error || 'ثبت نشد.');
      return;
    }
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
      if (!res.ok) { session.ok.disabled = false; say(session.err, res.error || 'بررسی نشد.'); return; }
      if (res.same) { closeSession(); return; }
      var send = function () { return post(r.dataset.saveUrl, a).then(afterSave); };
      if (res.is_new) {
        send().then(function () { if (session) session.ok.disabled = false; });
        return;
      }
      session.ok.disabled = false;
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

  var okBtn = dlg.querySelector('[data-pf-ok]');
  okBtn.addEventListener('click', function () {
    if (!dlg._ok || okBtn.disabled) return;
    okBtn.disabled = true;
    Promise.resolve(dlg._ok()).then(function () { okBtn.disabled = false; });
  });
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
