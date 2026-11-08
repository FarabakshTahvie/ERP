(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var pending = [];

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function track(p) {
    pending.push(p);
    var done = function () { var i = pending.indexOf(p); if (i > -1) pending.splice(i, 1); };
    p.then(done, done);
    return p;
  }
  window.fbUsageFlush = function () { return Promise.all(pending.slice()); };

  // برگه‌ی ارسال: دانلود ← «دانلود شد»؛ هر تغییر مصرف ← «دانلود نشده»
  function slipSet(stage, on) {
    var box = stage && stage.querySelector('[data-slip-box]');
    if (!box) return;
    box.dataset.downloaded = on ? '1' : '0';
    var badge = box.querySelector('[data-slip-badge]');
    if (!badge) return;
    badge.className = 'fb-badge ' + (on ? 'fb-badge-success' : 'fb-badge-warning');
    badge.textContent = on ? 'دانلود شد' : 'دانلود نشده';
  }
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('[data-slip-download]') : null;
    var box = a && a.closest('[data-slip-box]');
    if (box && box.dataset.tracked === '1') slipSet(box.closest('[id^="stage-"]'), true);
  });

  function say(cell, text, bad, keep) {
    cell.textContent = text || '';
    cell.className = 'text-xs ' + (bad ? 'text-error' : keep ? 'text-warning' : 'text-success');
    clearTimeout(cell._t);
    if (text && !bad && !keep) cell._t = setTimeout(function () { cell.textContent = ''; }, 3000);
  }
  function send(box, itemId, qty) {
    var fd = new FormData();
    fd.append('item_id', itemId);
    fd.append('qty', qty);
    return window.fbSend(box.dataset.url, fd, window.FB_CSRF);
  }

  // ذخیره‌ی لحظه‌ای: با خروج از کادر یا Enter
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches && e.target.matches('[data-usage-qty]')) {
      e.preventDefault();
      e.target.blur();
    }
  });
  document.addEventListener('change', function (e) {
    var input = e.target.closest ? e.target.closest('[data-usage-qty]') : null;
    if (!input) return;
    var row = input.closest('[data-usage-row]'), box = input.closest('[data-usage-box]');
    var msg = row.querySelector('[data-usage-msg]');
    var value = input.value.trim();
    if (value === input.dataset.saved) return;
    input.disabled = true;
    say(msg, 'در حال ذخیره...', false);
    track(send(box, row.dataset.item, value).then(function (res) {
      input.disabled = false;
      if (res.ok) {
        slipSet(input.closest('[id^="stage-"]'), false);
        input.value = res.qty;
        input.dataset.saved = res.qty;
        row.dataset.short = res.short || '';
        if (res.removed && row.dataset.extra === '1') { row.remove(); return; }
        if (res.short) say(msg, 'ذخیره شد؛ از انبار فقط بخشی کم شد (کسری ' + fa(res.short) + ')', false, true);
        else say(msg, res.removed ? 'پاک شد' : 'ذخیره شد', false);
      } else {
        input.value = input.dataset.saved;
        say(msg, res.error || 'ثبت نشد.', true);
      }
    }));
  });

  // افزودن کالای دیگر
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.hasAttribute || !form.hasAttribute('data-usage-add')) return;
    e.preventDefault();
    var box = form.closest('[data-usage-box]'), err = form.querySelector('[data-usage-add-error]');
    var itemId = form.querySelector('input[name=item_id]').value;
    var qty = form.querySelector('input[name=qty]').value.trim();
    var btn = form.querySelector('button[type=submit]');
    err.classList.add('hidden');
    function fail(text) { err.textContent = text; err.classList.remove('hidden'); }
    if (!itemId) { fail('کالا را از فهرست انتخاب کنید.'); return; }
    if (!qty) { fail('مقدار را بنویسید.'); return; }
    btn.disabled = true;
    window.fbUsageFlush().then(function () { return send(box, itemId, qty); }).then(function (res) {
      if (res.ok) {
        var stage = box.closest('[id^="stage-"]');
        if (stage) window.location.hash = stage.id;
        window.location.reload();
        return;
      }
      btn.disabled = false;
      fail(res.error || 'ثبت نشد.');
    });
  });

  // «تکمیل شد» صبر می‌کند تا ذخیره‌های در راه تمام شوند
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.hasAttribute || !form.hasAttribute('data-complete-form')) return;
    if (form._usageFlushed) { form._usageFlushed = false; return; }
    if (!pending.length) return;
    e.preventDefault();
    window.fbUsageFlush().then(function () {
      form._usageFlushed = true;
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  });

  // دلیل خدمت‌های نصب‌نشده: تا وقتی همه تیک نخورده‌اند، کادر دلیل نشان داده و اجباری می‌شود
  function syncUndone(stage) {
    if (!stage) return;
    var box = stage.querySelector('[data-undone-box]');
    if (!box) return;
    var some = false;
    stage.querySelectorAll('[data-install-check]').forEach(function (c) { if (!c.checked) some = true; });
    box.classList.toggle('hidden', !some);
    box.querySelector('[data-undone-reason]').required = some;
  }

  // تیک «انجام شد» خدمت‌های نصب (ثبت لحظه‌ای)
  document.addEventListener('change', function (e) {
    var cb = e.target.closest ? e.target.closest('[data-install-check]') : null;
    if (!cb) return;
    var row = cb.closest('[data-install-row]'), err = document.querySelector('[data-install-error]');
    var fd = new FormData();
    fd.append('service_id', row.dataset.service);
    fd.append('done', cb.checked ? '1' : '0');
    cb.disabled = true;
    function fail(text) { cb.checked = !cb.checked; syncUndone(cb.closest('[id^="stage-"]')); err.textContent = text; err.classList.remove('hidden'); }
    syncUndone(cb.closest('[id^="stage-"]'));
    track(window.fbSend(row.dataset.url, fd, window.FB_CSRF).then(function (res) {
      cb.disabled = false;
      if (res.ok) {
        err.classList.add('hidden');
        var counter = document.querySelector('[data-install-done]');
        if (counter) counter.textContent = fa(res.done);
      } else { fail(res.error || 'ثبت نشد.'); }
    }));
  });
  document.querySelectorAll('[data-undone-box]').forEach(function (b) { syncUndone(b.closest('[id^="stage-"]')); });
})();
