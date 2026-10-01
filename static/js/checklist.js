(function () {
  function say(el, text, ok) { el.textContent = text; el.className = 'text-xs ' + (ok ? 'text-success' : 'text-error'); }

  // ردیف‌های چک‌لیست: ✓ همان لحظه ذخیره می‌شود؛ ✗ بعد از نوشتن دلیل (دکمه‌ی «ثبت دلیل»)
  window.fbChecklistInit = function (root) {
    root.querySelectorAll('[data-check-row]').forEach(function (row) {
      var neg = row.dataset.neg, box = row.querySelector('[data-reason-box]'), reason = row.querySelector('[data-reason]');
      var qty = row.querySelector('[data-qty]'), qtyWrap = row.querySelector('[data-qty-wrap]');
      var msg = row.querySelector('[data-msg]'), btn = row.querySelector('[data-save-reason]');
      function cur() { var r = row.querySelector('input[type=radio]:checked'); return r ? r.value : null; }
      function save() {
        var st = cur(); if (!st) return;
        var isNeg = st === neg;
        if (isNeg && !reason.value.trim()) { say(msg, 'دلیل را بنویسید.', false); return; }
        var fd = new FormData();
        fd.append(row.dataset.idname, row.dataset.id); fd.append('status', st);
        fd.append('reason', isNeg ? reason.value : '');
        if (qty) fd.append('qty', isNeg ? '' : qty.value);
        say(msg, 'در حال ثبت...', true);
        window.fbSend(row.dataset.url, fd, window.FB_CSRF).then(function (res) {
          if (res.ok) say(msg, 'ثبت شد', true); else say(msg, res.error || 'ثبت نشد', false);
        });
      }
      row.addEventListener('change', function (e) {
        if (e.target.matches('input[type=radio]')) {
          var isNeg = e.target.value === neg;
          if (box) box.classList.toggle('hidden', !isNeg);
          if (qtyWrap) qtyWrap.classList.toggle('hidden', isNeg);
          if (isNeg) { if (reason) reason.focus(); } else save();
        } else if (qty && e.target === qty && cur() && cur() !== neg) save();
      });
      if (btn) btn.addEventListener('click', save);
    });
  };

  // فرم‌های کوچک (افزودن/حذف) با fetch؛ بعد از موفقیت صفحه تازه می‌شود
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('[data-ops-form]'); if (!f) return;
    e.preventDefault();
    if (f.dataset.confirm && !window.confirm(f.dataset.confirm)) return;
    var err = f.querySelector('[data-form-error]'), b = f.querySelector('button[type=submit]');
    if (b) b.disabled = true;
    window.fbSend(f.action, new FormData(f), window.FB_CSRF).then(function (res) {
      if (b) b.disabled = false;
      if (res.ok) { window.location.reload(); return; }
      if (err) { err.textContent = res.error || 'ثبت نشد.'; err.classList.remove('hidden'); } else alert(res.error || 'ثبت نشد.');
    });
  });
  document.addEventListener('click', function (e) {
    var o = e.target.closest('[data-open-dialog]');
    if (o) document.getElementById(o.dataset.openDialog).showModal();
  });

  window.fbOpsPickers = function (items) {
    document.querySelectorAll('[data-item-picker]').forEach(function (m) {
      var hid = m.parentElement.querySelector('input[name=item_id]');
      var p = window.fbItemPicker({ items: items, ariaLabel: 'انتخاب کالا', onSelect: function (it) { hid.value = it ? it.id : ''; } });
      m.appendChild(p.el);
    });
  };
})();
