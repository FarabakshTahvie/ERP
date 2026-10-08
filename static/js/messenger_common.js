(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var M = window.fbMsgr = {};
  var rootEl = document.querySelector('[data-msgr-root]');
  M.spriteUrl = rootEl ? rootEl.dataset.sprite : '';

  M.fa = function (n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); };
  M.norm = function (s) { return String(s || '').replace(/ي/g, 'ی').replace(/ك/g, 'ک').toLowerCase().trim(); };
  M.el = function (tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };
  M.icon = function (name, cls) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', cls || 'w-4 h-4');
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', M.spriteUrl + '#' + name);
    svg.appendChild(use);
    return svg;
  };
  M.avatar = function (name, isGroup, width) {
    var box = M.el('div', 'avatar avatar-placeholder shrink-0');
    var c = M.el('div', (isGroup ? 'bg-primary text-primary-content' : 'bg-neutral text-neutral-content') +
                 ' rounded-full ' + (width || 'w-10'));
    if (isGroup) c.appendChild(M.icon('users', 'w-5 h-5'));
    else c.appendChild(M.el('span', null, String(name || '?').trim().charAt(0)));
    box.appendChild(c);
    return box;
  };
  M.uuid = function () {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    var b = crypto.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var h = Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  };

  var tf = new Intl.DateTimeFormat('fa-IR', { hour: '2-digit', minute: '2-digit', hour12: false });
  var df = new Intl.DateTimeFormat('fa-IR', { weekday: 'long', day: 'numeric', month: 'long' });
  var sf = new Intl.DateTimeFormat('fa-IR', { day: 'numeric', month: 'short' });
  function sameDay(a, b) { return a.toDateString() === b.toDateString(); }
  M.clock = function (iso) { return tf.format(new Date(iso)); };
  M.dayLabel = function (ts) {
    var d = new Date(ts * 1000), now = new Date(), y = new Date(now.getTime() - 86400000);
    return sameDay(d, now) ? 'امروز' : sameDay(d, y) ? 'دیروز' : df.format(d);
  };
  M.listTime = function (iso) {
    var d = new Date(iso);
    return sameDay(d, new Date()) ? tf.format(d) : sf.format(d);
  };

  // متن ساده + لینک‌های http/https (فقط با createElement)
  M.fill = function (parent, text) {
    var re = /https?:\/\/[^\s<>"']+/g, last = 0, m;
    while ((m = re.exec(text))) {
      if (m.index > last) parent.appendChild(document.createTextNode(text.slice(last, m.index)));
      var a = M.el('a', 'underline', m[0]);
      a.href = m[0]; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.dir = 'ltr';
      parent.appendChild(a);
      last = m.index + m[0].length;
    }
    if (last < text.length) parent.appendChild(document.createTextNode(text.slice(last)));
  };

  // همیشه resolve می‌شود با {ok, ...}
  M.api = function (url, data) {
    var opts = { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } };
    if (data) {
      var fd = new FormData();
      Object.keys(data).forEach(function (k) { if (data[k] != null) fd.append(k, data[k]); });
      opts.method = 'POST'; opts.body = fd;
      opts.headers['X-CSRFToken'] = window.FB_CSRF;
    }
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (j) { j.status = r.status; return j; }, function () {
        return { ok: false, status: r.status, error: 'نشست شما تمام شده یا صفحه پیدا نشد؛ صفحه را دوباره باز کنید.' };
      });
    }, function () { return { ok: false, network: true, error: 'اتصال برقرار نشد.' }; });
  };

  // اجرای دوره‌ای فقط وقتی تب دیده می‌شود؛ هم‌پوشانی ندارد
  M.poll = function (fn, ms) {
    var busy = false;
    function tick() {
      if (document.hidden || busy) return;
      busy = true;
      Promise.resolve(fn()).catch(function () {}).then(function () { busy = false; });
    }
    setInterval(tick, ms);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) tick(); });
    window.addEventListener('online', tick);
    window.addEventListener('pageshow', function (e) { if (e.persisted) tick(); });
    return { now: tick };
  };

  M.setBadge = function (n) {
    document.querySelectorAll('[data-msgr-badge]').forEach(function (b) {
      b.textContent = M.fa(n > 99 ? '99+' : n);
      b.classList.toggle('hidden', !n);
    });
  };

  // مودال تایید مشترک (dialog باید در صفحه‌ی میزبان باشد)
  M.confirm = function (opts, onOk) {
    var dlg = document.querySelector('[data-msgr-confirm]');
    if (!dlg) return;
    dlg.querySelector('[data-confirm-title]').textContent = opts.title || '';
    dlg.querySelector('[data-confirm-text]').textContent = opts.text || '';
    var ok = dlg.querySelector('[data-confirm-ok]');
    ok.textContent = opts.ok || 'تایید';
    ok.className = 'btn btn-sm ' + (opts.danger ? 'btn-soft btn-error' : 'btn-primary');
    ok.onclick = function () { dlg.close(); onOk(); };
    dlg.showModal();
  };
})();
