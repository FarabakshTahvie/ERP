(function () {
  var form = document.querySelector('[data-purchase-line-form]');
  if (!form || !window.fbItemPicker || !window.fbSend) return;
  var toggle = document.querySelector('[data-line-toggle]');
  var tbody = document.querySelector('[data-purchase-lines]');
  var err = form.querySelector('[data-line-error]'), okMsg = form.querySelector('[data-line-ok]');
  var hidden = form.querySelector('input[name=item_id]');
  var qty = form.querySelector('input[name=qty]'), cost = form.querySelector('input[name=unit_cost]');
  var btn = form.querySelector('button[type=submit]');
  var items = JSON.parse((document.getElementById('purchase-line-items') || {}).textContent || '[]');
  var picker = window.fbItemPicker({ items: items, ariaLabel: 'انتخاب کالا', onSelect: function (it) { hidden.value = it ? it.id : ''; } });
  form.querySelector('[data-line-picker]').appendChild(picker.el);
  var pickerInput = picker.el.querySelector('input');

  function digits(v) { return window.fbMoney ? window.fbMoney.digits(v) : String(v).replace(/\D/g, ''); }
  function setOpen(open) {
    form.classList.toggle('hidden', !open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) picker.focus();
  }
  function say(node, text) {
    err.classList.add('hidden'); okMsg.classList.add('hidden');
    if (!text) return;
    node.textContent = text;
    node.classList.remove('hidden');
  }
  function cell(text, cls) {
    var td = document.createElement('td');
    if (cls) td.className = cls;
    td.textContent = text;
    return td;
  }
  function addRow(l) {
    var empty = tbody.querySelector('[data-empty-row]');
    if (empty) empty.remove();
    var tr = document.createElement('tr');
    tr.appendChild(cell(l.item, 'font-semibold'));
    tr.appendChild(cell(l.qty + ' ' + l.unit, 'font-technical'));
    tr.appendChild(cell(l.unit_cost, 'font-technical'));
    tr.appendChild(cell(l.total, 'font-technical font-semibold'));
    tbody.appendChild(tr);
    if (tr.scrollIntoView) tr.scrollIntoView({ block: 'nearest' });
  }
  function setText(sel, text) {
    document.querySelectorAll(sel).forEach(function (n) { n.textContent = text; });
  }

  toggle.addEventListener('click', function () { setOpen(form.classList.contains('hidden')); });
  form.querySelector('[data-line-close]').addEventListener('click', function () { setOpen(false); });
  document.addEventListener('fb:item-created', function (e) {
    picker.addItem(e.detail);
    picker.select(e.detail.id);
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var q = qty.value.trim(), c = digits(cost.value);
    if (!hidden.value) { say(err, 'کالا را از فهرست انتخاب کنید.'); return; }
    if (!q) { say(err, 'مقدار را بنویسید.'); return; }
    if (!c) { say(err, 'بهای واحد را بنویسید.'); return; }
    say(null, '');
    btn.disabled = true;
    var fd = new FormData();
    fd.append('item_id', hidden.value);
    fd.append('qty', q);
    fd.append('unit_cost', c);
    window.fbSend(form.dataset.url, fd, window.FB_CSRF).then(function (res) {
      btn.disabled = false;
      if (!res.ok) { say(err, res.error || 'ثبت نشد.'); return; }
      addRow(res.line);
      setText('[data-stat="purchase-count"]', res.count);
      setText('[data-stat="purchase-total"]', res.grand_total);
      setText('[data-purchase-total]', res.grand_total);
      hidden.value = ''; pickerInput.value = ''; qty.value = ''; cost.value = '';
      say(okMsg, 'ردیف اضافه شد. کالای بعدی را بنویسید یا «بستن» را بزنید.');
      picker.focus();
    });
  });
})();
