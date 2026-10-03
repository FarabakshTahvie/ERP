(function () {
  var nf = new Intl.NumberFormat('fa-IR');
  var FA = '۰۱۲۳۴۵۶۷۸۹', AR = '٠١٢٣٤٥٦٧٨٩';
  function fmt(n) { return nf.format(Math.round(n || 0)).replace(/٬/g, ','); }
  function clean(s) {
    return String(s == null ? '' : s)
      .replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return AR.indexOf(d); })
      .replace(/[,٬\s]/g, '').replace(/٫/g, '.');
  }
  function num(s) { var v = parseFloat(clean(s)); return isNaN(v) ? 0 : v; }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function buildCell(col, value, notify) {
    var wrap = el('div', 'flex flex-col gap-1 ' + (col.cls || 'flex-1 min-w-40'));
    if (col.label) wrap.appendChild(el('span', 'text-xs fb-muted', col.label));
    var cell = { el: wrap };
    if (col.type === 'picker') {
      var picker = window.fbItemPicker({
        items: col.items, placeholder: col.placeholder, ariaLabel: col.label,
        onSelect: function () { notify(); }
      });
      wrap.appendChild(picker.el);
      cell.get = function () { return picker.getId(); };
      if (value != null && value !== '') picker.select(parseInt(value, 10));
    } else if (col.type === 'readonly') {
      var out = el('span', 'font-technical text-sm py-1.5', '—');
      wrap.appendChild(out);
      cell.set = function (t) { out.textContent = t; };
    } else if (col.type === 'checkbox') {
      var box = el('input', 'checkbox checkbox-sm');
      box.type = 'checkbox';
      box.checked = value === true || value === '1';
      box.addEventListener('change', notify);
      wrap.appendChild(box);
      cell.get = function () { return box.checked; };
    } else if (col.type === 'select') {
      var sel = el('select', 'select select-sm w-full');
      (col.options || []).forEach(function (o) { var op = el('option', null, o[1]); op.value = o[0]; sel.appendChild(op); });
      if (value) sel.value = value;
      sel.addEventListener('change', notify);
      wrap.appendChild(sel);
      cell.get = function () { return sel.value; };
    } else {
      var input = el('input', 'input input-sm w-full' + (col.type === 'text' ? '' : ' font-technical'));
      input.type = 'text';
      input.autocomplete = 'off';
      input.placeholder = col.placeholder || '';
      if (col.type !== 'text') {
        input.setAttribute('inputmode', col.type === 'money' ? 'numeric' : 'decimal');
        input.dir = 'ltr';
      }
      if (value != null) input.value = value;
      input.addEventListener('input', notify);
      wrap.appendChild(input);
      cell.get = function () { return input.value; };
    }
    return cell;
  }

  function makeLevel(spec, box, notify) {
    var level = { rows: [] };
    level.addRow = function (values) {
      values = values || {};
      var rowEl = el('div', 'fb-inset flex flex-col gap-2');
      var cellsEl = el('div', 'flex flex-wrap items-end gap-2');
      rowEl.appendChild(cellsEl);
      var row = { el: rowEl, pk: values.pk || null, cells: {}, children: null, footer: null };
      spec.columns.forEach(function (col) {
        row.cells[col.key] = buildCell(col, values[col.key], notify);
        cellsEl.appendChild(row.cells[col.key].el);
      });
      var rm = el('button', 'btn btn-soft btn-error btn-sm', 'حذف');
      rm.type = 'button';
      rm.setAttribute('aria-label', 'حذف ردیف');
      rm.addEventListener('click', function () {
        rowEl.remove();
        level.rows.splice(level.rows.indexOf(row), 1);
        notify();
      });
      cellsEl.appendChild(rm);
      if (spec.children) {
        var kids = el('div', 'flex flex-col gap-2 border-s border-base-300 ps-3');
        kids.appendChild(el('div', 'text-xs fb-muted font-semibold', spec.children.title));
        var kidsRows = el('div', 'flex flex-col gap-2');
        kids.appendChild(kidsRows);
        var addKid = el('button', 'btn btn-ghost btn-sm self-start', spec.children.addLabel);
        addKid.type = 'button';
        row.children = makeLevel(spec.children, kidsRows, notify);
        addKid.addEventListener('click', function () { row.children.addRow(); notify(); });
        kids.appendChild(addKid);
        rowEl.appendChild(kids);
        (values[spec.children.key] || []).forEach(function (k) { row.children.addRow(k); });
      }
      if (spec.footer) {
        row.footer = el('div', 'text-xs fb-muted');
        rowEl.appendChild(row.footer);
      }
      level.rows.push(row);
      box.appendChild(rowEl);
      return row;
    };
    return level;
  }

  function values(row, spec) {
    var d = {};
    spec.columns.forEach(function (c) { if (c.type !== 'readonly') d[c.key] = row.cells[c.key].get(); });
    if (spec.children) {
      d[spec.children.key] = row.children.rows.map(function (k) { return values(k, spec.children); });
    }
    return d;
  }

  function recompute(level, spec, parent) {
    level.rows.forEach(function (row) {
      var d = values(row, spec);
      spec.columns.forEach(function (c) {
        if (c.type === 'readonly' && c.compute) row.cells[c.key].set(c.compute(d, parent));
      });
      if (spec.children) recompute(row.children, spec.children, d);
      if (row.footer && spec.footer) row.footer.textContent = spec.footer(d);
    });
  }

  function serialize(level, spec) {   // ردیف کاملاً خالی ارسال نمی‌شود؛ ردیف ناقص می‌رود تا سرور خطای واضح بدهد
    var out = [];
    level.rows.forEach(function (row) {
      var d = values(row, spec), filled = !!row.pk;
      if (row.pk) d.pk = row.pk;
      spec.columns.forEach(function (c) {
        if (c.type === 'readonly' || c.type === 'checkbox' || c.type === 'select') return;
        var v = d[c.key];
        if (v !== null && v !== undefined && String(v).trim() !== '') filled = true;
      });
      if (spec.children) {
        d[spec.children.key] = serialize(row.children, spec.children);
        if (d[spec.children.key].length) filled = true;
        d[spec.children.key].forEach(function () {});
      }
      if (filled) out.push(d);
    });
    return out;
  }

  window.fbLineEditor = function (cfg) {
    var root = cfg.mount, hidden = cfg.hidden, loading = true;
    var rowsBox = el('div', 'flex flex-col gap-3');
    var empty = el('p', 'fb-hint', cfg.emptyText || 'هنوز ردیفی اضافه نشده.');
    var add = el('button', 'btn btn-soft btn-sm self-start', cfg.addLabel || 'افزودن ردیف');
    add.type = 'button';
    root.appendChild(rowsBox); root.appendChild(empty); root.appendChild(add);
    var top;
    function notify() {
      if (loading) return;
      recompute(top, cfg, null);
      var data = serialize(top, cfg);
      hidden.value = JSON.stringify(data);
      empty.classList.toggle('hidden', top.rows.length > 0);
      if (cfg.onChange) cfg.onChange(data);
    }
    top = makeLevel(cfg, rowsBox, notify);
    hidden.name = hidden.dataset.name || hidden.name;   // اگر JS اجرا نشود، فیلد ارسال نمی‌شود (سرور دست نمی‌زند)
    add.addEventListener('click', function () { top.addRow(); notify(); });
    (cfg.initial || []).forEach(function (r) { top.addRow(r); });
    loading = false;
    notify();
    return { notify: notify };
  };
  window.fbLineEditor.num = num;
  window.fbLineEditor.fmt = fmt;
})();
