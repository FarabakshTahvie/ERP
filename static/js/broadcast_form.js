(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function parts(n) { return n <= 70 ? 1 : Math.ceil(n / 67); }

  function initAudience(form) {
    function sync() {
      var r = form.querySelector('input[name="audience_kind"]:checked'), kind = r ? r.value : '';
      form.querySelectorAll('[data-audience-panel]').forEach(function (p) {
        p.classList.toggle('hidden', p.dataset.audiencePanel !== kind);
      });
    }
    form.querySelectorAll('input[name="audience_kind"]').forEach(function (r) { r.addEventListener('change', sync); });
    sync();
    var mount = form.querySelector('[data-audience-picker]');
    if (mount && window.fbRemotePicker) {
      var initial = [];
      try { initial = JSON.parse(document.getElementById(mount.dataset.initialId).textContent || '[]'); } catch (e) {}
      mount.appendChild(window.fbRemotePicker({ url: mount.dataset.url, multi: true, name: 'audience_users',
                                                initial: initial, ariaLabel: 'جستجوی کاربر' }));
    }
  }

  function initCommon(form) {
    form.querySelectorAll('[data-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        var input = form.querySelector('input[name="link_path"]');
        if (input) input.value = b.dataset.preset;
        input && input.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });
    form.querySelectorAll('[data-counter]').forEach(function (input) {
      var out = document.getElementById(input.dataset.counter);
      function upd() { if (out) out.textContent = fa(input.value.length); }
      input.addEventListener('input', upd); upd();
    });
  }

  function initPush(form) {
    var title = form.querySelector('[name="title"]'), body = form.querySelector('[name="body"]');
    var lt = form.querySelector('[data-live-title]'), lb = form.querySelector('[data-live-body]');
    function upd() {
      lt.textContent = title.value || 'عنوان';
      lb.textContent = body.value || 'متن پیام اینجا دیده می‌شود.';
    }
    title.addEventListener('input', upd); body.addEventListener('input', upd); upd();
  }

  function initSms(form) {
    var body = form.querySelector('[data-sms-body]'), link = form.querySelector('[data-sms-link]');
    var count = form.querySelector('[data-sms-count]'), pc = form.querySelector('[data-sms-parts]');
    var warn = form.querySelector('[data-sms-warn]');
    var sig = parseInt(form.dataset.sigLen, 10), linkLen = parseInt(form.dataset.linkLen, 10);
    function upd() {
      var n = body.value.length + sig + (link.value.trim() ? linkLen : 0);
      count.textContent = fa(n); pc.textContent = fa(parts(n));
      warn.classList.toggle('hidden', n <= 320);
    }
    ['input', 'change'].forEach(function (ev) { body.addEventListener(ev, upd); link.addEventListener(ev, upd); });
    upd();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-broadcast-form]').forEach(function (f) {
      initAudience(f); initCommon(f);
      if (f.dataset.broadcastForm === 'push') initPush(f); else initSms(f);
    });
  });
})();