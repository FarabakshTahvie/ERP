(function () {
  function legacyCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) {}
    area.remove();
    return ok;
  }
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-copy]') : null;
    if (!btn) return;
    var use = btn.querySelector('use');
    copyText(btn.dataset.copy).then(function (ok) {
      if (!use) return;
      if (!btn._orig) btn._orig = use.getAttribute('href');
      use.setAttribute('href', btn._orig.replace(/#.*$/, ok ? '#check' : '#x'));
      clearTimeout(btn._timer);
      btn._timer = setTimeout(function () { use.setAttribute('href', btn._orig); }, 1500);
    });
  });

  function initSlider(root) {
    var track = root.querySelector('[data-track]');
    if (!track || track.children.length < 2) return;
    var kids = track.children;
    var dots = root.querySelectorAll('[data-dot]');
    function step() { return Math.abs(kids[1].offsetLeft - kids[0].offsetLeft) || track.clientWidth; }
    function paint() {
      var s = step();
      if (!s) return;
      var now = Math.min(kids.length - 1, Math.round(Math.abs(track.scrollLeft) / s));
      Array.prototype.forEach.call(dots, function (d, i) {
        d.classList.toggle('bg-primary', i === now);
        d.classList.toggle('bg-base-content/20', i !== now);
      });
    }
    var queued = false;
    track.addEventListener('scroll', function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; paint(); });
    }, { passive: true });
    root.querySelectorAll('[data-slide]').forEach(function (b) {
      b.addEventListener('click', function () {
        var rtl = getComputedStyle(track).direction === 'rtl';
        track.scrollBy({ left: (+b.dataset.slide) * step() * (rtl ? -1 : 1), behavior: 'smooth' });
      });
    });
    paint();
  }

  // مودال‌های کارت (ثبت و ویرایش)؛ خطا داخل خود مودال دیده می‌شود
  function initCardForms() {
    if (!window.fbSend) return;
    document.querySelectorAll('[data-bankcard-form]').forEach(function (form) {
      var bank = form.querySelector('[name="bank"]');
      var otherBox = form.querySelector('[data-other-bank]');
      var err = form.querySelector('[data-bankcard-error]');
      var btn = form.querySelector('button[type="submit"]');
      function syncOther() { otherBox.classList.toggle('hidden', bank.value !== 'other'); }
      bank.addEventListener('change', syncOther);
      syncOther();
      form._syncOther = syncOther;
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var url = form.getAttribute('action');
        if (!url) return;
        err.classList.add('hidden');
        btn.disabled = true;
        window.fbSend(url, new FormData(form), window.FB_CSRF).then(function (res) {
          if (res.ok) { window.location.reload(); return; }
          btn.disabled = false;
          err.textContent = res.error || 'ثبت نشد.';
          err.classList.remove('hidden');
        });
      });
    });
  }

  function listError(text) {
    var box = document.querySelector('[data-bankcard-list-error]');
    if (!box) return;
    box.textContent = text || '';
    box.classList.toggle('hidden', !text);
  }

  // دکمه‌های فهرست مدیریت: ویرایش، فعال/غیرفعال، حذف (شنونده‌ی تفویضی)
  document.addEventListener('click', function (e) {
    if (!window.fbSend || !e.target.closest) return;

    var edit = e.target.closest('[data-bankcard-edit]');
    if (edit) {
      var editDialog = document.getElementById('bankcard-edit-dialog');
      var editForm = editDialog && editDialog.querySelector('[data-bankcard-form]');
      if (!editForm) return;
      var d = edit.dataset;
      editForm.setAttribute('action', d.url);
      editForm.querySelector('[name="bank"]').value = d.bank;
      editForm.querySelector('[name="other_bank_name"]').value = d.other;
      editForm.querySelector('[name="holder_name"]').value = d.holder;
      editForm.querySelector('[name="card_number"]').value = d.number;
      editForm.querySelector('[name="sheba"]').value = d.sheba;
      editForm.querySelector('[name="cvv2"]').value = d.cvv2;
      editForm.querySelector('[name="expiry"]').value = d.expiry;
      editForm._syncOther();
      editForm.querySelector('[data-bankcard-error]').classList.add('hidden');
      editForm.querySelector('button[type="submit"]').disabled = false;
      editDialog.showModal();
      return;
    }

    var sw = e.target.closest('[data-bankcard-active]');
    if (sw) {
      listError('');
      sw.disabled = true;
      var swData = new FormData();
      swData.append('active', sw.dataset.next);
      window.fbSend(sw.dataset.url, swData, window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        sw.disabled = false;
        listError(res.error || 'ثبت نشد.');
      });
      return;
    }

    var del = e.target.closest('[data-bankcard-delete]');
    if (del) {
      var delDialog = document.getElementById('bankcard-delete-dialog');
      if (!delDialog) return;
      delDialog.querySelector('[data-delete-label]').textContent = del.dataset.label;
      delDialog.querySelector('[data-delete-error]').classList.add('hidden');
      var delOk = delDialog.querySelector('[data-delete-ok]');
      delOk.dataset.url = del.dataset.url;
      delOk.disabled = false;
      delDialog.showModal();
      return;
    }

    var confirmBtn = e.target.closest('[data-delete-ok]');
    if (confirmBtn && confirmBtn.dataset.url) {
      var delErr = document.querySelector('[data-delete-error]');
      delErr.classList.add('hidden');
      confirmBtn.disabled = true;
      window.fbSend(confirmBtn.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        confirmBtn.disabled = false;
        delErr.textContent = res.error || 'حذف نشد.';
        delErr.classList.remove('hidden');
      });
    }
  });

  function init() {
    document.querySelectorAll('[data-bankcards]').forEach(initSlider);
    initCardForms();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
