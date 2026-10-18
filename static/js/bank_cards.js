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

  // ثبت کارت تازه از مودال (فقط مدیر و حسابدار)؛ خطا داخل خود مودال دیده می‌شود
  function initCardForm() {
    var form = document.querySelector('[data-bankcard-form]');
    if (!form || !window.fbSend) return;
    var bank = form.querySelector('[name="bank"]');
    var otherBox = form.querySelector('[data-other-bank]');
    var err = form.querySelector('[data-bankcard-error]');
    var btn = form.querySelector('button[type="submit"]');
    function syncOther() { otherBox.classList.toggle('hidden', bank.value !== 'other'); }
    bank.addEventListener('change', syncOther);
    syncOther();
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      err.classList.add('hidden');
      btn.disabled = true;
      window.fbSend(form.action, new FormData(form), window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        btn.disabled = false;
        err.textContent = res.error || 'ثبت نشد.';
        err.classList.remove('hidden');
      });
    });
  }

  function init() {
    document.querySelectorAll('[data-bankcards]').forEach(initSlider);
    initCardForm();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
