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
  function icon(sprite, name) {
    if (!sprite) return null;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'w-4 h-4');
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', sprite + '#' + name);
    svg.appendChild(use);
    return svg;
  }
  // دکمه‌ی «افزودن»: خط‌چین و رنگ برند تا از نگاه اول دیده شود
  function addButton(label, sprite) {
    var b = el('button', 'btn btn-dash btn-primary btn-sm w-full');
    b.type = 'button';
    var ic = icon(sprite, 'plus');
    if (ic) b.appendChild(ic);
    b.appendChild(el('span', null, label));
    return b;
  }

  function buildCell(col, value, notify) {
    var wrap = el('div', 'flex flex-col gap-1 ' + (col.cls || 'flex-1 min-w-40') + (col.type === 'readonly' ? ' items-center text-center' : ''));
    if (col.label) wrap.appendChild(el('span', 'text-xs fb-muted' + (col.center ? ' self-center' : ''), col.label));
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
      var input = el('input', 'input input-sm w-full' + (col.type === 'text' ? '' : ' font-technical') + (col.center ? ' text-center' : ''));
      input.type = 'text';
      input.autocomplete = 'off';
      input.placeholder = col.placeholder || '';
      if (col.type !== 'text') {
        input.setAttribute('inputmode', col.type === 'money' ? 'numeric' : 'decimal');
        input.dir = 'ltr';
        input.setAttribute(col.type === 'money' ? 'data-money' : 'data-decimal', '1');
        if (col.type === 'money') input.maxLength = 12;
      }
      if (value != null) input.value = value;
      if (col.type === 'money' && window.fbMoney) window.fbMoney.format(input);
      if (col.auto) {
        // کادری که خودکار پر می‌شود؛ هر چیزی که کاربر بنویسد «دستی» است و خالی‌کردنش به خودکار برمی‌گردد
        var mark = el('span', 'text-xs fb-muted text-center hidden', 'دستی؛ برای خودکار، خالی کنید');
        cell.manual = value != null && String(value).trim() !== '';
        mark.classList.toggle('hidden', !cell.manual);
        input.addEventListener('input', function () {
          cell.manual = input.value.trim() !== '';
          mark.classList.toggle('hidden', !cell.manual);
          notify();
        });
        cell.setAuto = function (text) {
          if (cell.manual) return;
          input.value = text;
          if (window.fbMoney) window.fbMoney.format(input);
        };
        cell.get = function () { return cell.manual ? input.value : ''; };
        wrap.appendChild(input);
        wrap.appendChild(mark);
      } else {
        input.addEventListener('input', notify);
        cell.get = function () { return input.value; };
        wrap.appendChild(input);
      }
    }
    return cell;
  }

  function paintFooter(node, note) {
    var isObject = !!note && typeof note === 'object';
    var text = isObject ? note.text : (note || '');
    var tone = isObject ? note.tone : '';
    node.textContent = text;
    node.className = tone === 'warning' ? 'alert alert-soft alert-warning text-xs py-1.5' : 'text-xs fb-muted';
    node.classList.toggle('hidden', !text);
  }

  function makeLevel(spec, box, notify, ctx) {
    var level = { rows: [] };
    level.addRow = function (values) {
      values = values || {};
      var rowEl = el('div', ctx.nested
        ? 'flex flex-col gap-2 py-3 border-t border-base-300 first:border-t-0 first:pt-0'
        : 'fb-inset flex flex-col gap-2');
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
        var kidsRows = el('div', 'flex flex-col');
        kids.appendChild(kidsRows);
        var addKid = addButton(spec.children.addLabel, ctx.sprite);
        row.children = makeLevel(spec.children, kidsRows, notify, { sprite: ctx.sprite, nested: true });
        addKid.addEventListener('click', function () { row.children.addRow(); notify(); });
        kids.appendChild(addKid);
        rowEl.appendChild(kids);
        (values[spec.children.key] || []).forEach(function (k) { row.children.addRow(k); });
      }
      if (spec.footer) {
        row.footer = el('div', 'text-xs fb-muted hidden');
        row.footer.setAttribute('role', 'status');
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
        var cell = row.cells[c.key];
        if (c.type === 'readonly' && c.compute) cell.set(c.compute(d, parent));
        else if (c.auto && cell.setAuto) cell.setAuto(c.auto(d, parent));
      });
      if (spec.children) recompute(row.children, spec.children, d);
      if (row.footer && spec.footer) paintFooter(row.footer, spec.footer(d, parent));
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
      }
      if (filled) out.push(d);
    });
    return out;
  }

  window.fbLineEditor = function (cfg) {
    var root = cfg.mount, hidden = cfg.hidden, loading = true;
    var sprite = root.dataset.sprite || '';
    root.classList.add('flex', 'flex-col', 'gap-3');
    var rowsBox = el('div', 'flex flex-col gap-3 empty:hidden');
    var empty = el('p', 'fb-hint', cfg.emptyText || 'هنوز ردیفی اضافه نشده.');
    var add = addButton(cfg.addLabel || 'افزودن ردیف', sprite);
    root.appendChild(rowsBox); root.appendChild(empty); root.appendChild(add);
    var top;
    function notify() {
      if (loading) return;
      var data = serialize(top, cfg);
      if (cfg.prepare) cfg.prepare(data);   // قبل از محاسبه؛ مثلاً جمع نیاز هر کالا در کل پیش‌فاکتور
      recompute(top, cfg, null);
      hidden.value = JSON.stringify(data);
      empty.classList.toggle('hidden', top.rows.length > 0);
      if (cfg.onChange) cfg.onChange(data);
    }
    top = makeLevel(cfg, rowsBox, notify, { sprite: sprite, nested: false });
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
