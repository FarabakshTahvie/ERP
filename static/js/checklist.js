(function () {
  // فرم‌های کوچک با fetch؛ بعد از موفقیت صفحه تازه می‌شود
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

  window.fbOpsPickers = function (items) {
    document.querySelectorAll('[data-item-picker]').forEach(function (m) {
      var hid = m.parentElement.querySelector('input[name=item_id]');
      var p = window.fbItemPicker({ items: items, ariaLabel: 'انتخاب کالا', onSelect: function (it) { hid.value = it ? it.id : ''; } });
      m.appendChild(p.el);
    });
  };
})();
