(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹', MAX_BYTES = 25 * 1024 * 1024;
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function clean(s) { return String(s || '').replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); }).replace(/[٠-٩]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.indexOf(d); }).trim(); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sizeText(b) { return b >= 1048576 ? fa((b / 1048576).toFixed(1)) + ' مگابایت' : fa(Math.max(1, Math.round(b / 1024))) + ' کیلوبایت'; }

  function send(url, formData, csrf, onProgress) {   // همیشه resolve می‌شود با {ok, ...}
    return new Promise(function (resolve) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.setRequestHeader('X-CSRFToken', csrf || window.FB_CSRF || '');
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      if (onProgress) xhr.upload.onprogress = function (e) { if (e.lengthComputable) onProgress(Math.round(e.loaded / e.total * 100)); };
      xhr.onload = function () {
        if (xhr.status === 413) return resolve({ ok: false, error: 'حجم فایل بیشتر از ۲۵ مگابایت است.' });
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (err) {}
        resolve(data || { ok: false, error: 'پاسخ نامعتبر از سرور (کد ' + fa(xhr.status) + ').' });
      };
      xhr.onerror = function () { resolve({ ok: false, error: 'اتصال قطع شد؛ دوباره تلاش کنید.' }); };
      xhr.send(formData);
    });
  }
  window.fbSend = send;

  function dropzone(root) {
    var cfg = { mode: root.dataset.mode || 'instant', url: root.dataset.url || '', cuts: root.dataset.cuts === '1', anchor: root.dataset.anchor || '' };
    var items = [], busy = false;

    var drop = el('div', 'fb-inset flex flex-col items-center gap-2 text-center py-5 border border-dashed border-base-300');
    drop.appendChild(el('span', 'text-sm', 'فایل‌ها را اینجا رها کنید یا انتخاب کنید'));
    var input = el('input', 'sr-only'); input.type = 'file'; input.multiple = true; input.setAttribute('aria-label', 'انتخاب فایل');
    var pick = el('button', 'btn btn-soft btn-sm', 'انتخاب فایل'); pick.type = 'button';
    pick.addEventListener('click', function () { input.click(); });
    drop.appendChild(pick); drop.appendChild(input);
    var list = el('div', 'flex flex-col gap-2');
    var actions = el('div', 'flex gap-2 hidden');
    var go = null;
    if (cfg.mode === 'instant') { go = el('button', 'btn btn-primary btn-sm', 'ارسال فایل‌ها'); go.type = 'button'; actions.appendChild(go); }
    var clear = el('button', 'btn btn-ghost btn-sm', 'پاک‌کردن فهرست'); clear.type = 'button';
    actions.appendChild(clear);
    var note = el('p', 'text-xs text-error hidden', 'ارسال برخی فایل‌ها ناموفق بود. دوباره تلاش کنید.');
    [drop, list, actions, note].forEach(function (n) { root.appendChild(n); });

    function refresh() { actions.classList.toggle('hidden', !items.length); }
    function fail(it, msg) { it.state = 'error'; it.status.textContent = msg; it.status.className = 'text-xs text-error'; }

    function addFiles(files) {
      Array.prototype.forEach.call(files, function (file) {
        var row = el('div', 'fb-inset flex flex-col gap-1.5');
        var top = el('div', 'flex items-center gap-2');
        var name = el('span', 'text-xs flex-1 min-w-0 break-all', file.name); name.dir = 'auto';
        top.appendChild(name);
        top.appendChild(el('span', 'text-xs fb-muted shrink-0', sizeText(file.size)));
        var it = { file: file, state: 'ready', row: row };
        if (cfg.cuts) {
          it.cut = el('input', 'input input-sm w-16 font-technical'); it.cut.type = 'text'; it.cut.value = '1';
          it.cut.setAttribute('inputmode', 'numeric'); it.cut.dir = 'ltr'; it.cut.setAttribute('aria-label', 'تعداد برش');
          top.appendChild(el('span', 'text-xs fb-muted shrink-0', 'برش:')); top.appendChild(it.cut);
        }
        it.rm = el('button', 'btn btn-ghost btn-xs', 'حذف'); it.rm.type = 'button';
        it.rm.addEventListener('click', function () { if (busy) return; row.remove(); items.splice(items.indexOf(it), 1); refresh(); });
        top.appendChild(it.rm);
        it.bar = el('progress', 'progress progress-primary w-full'); it.bar.max = 100; it.bar.value = 0;
        it.status = el('span', 'text-xs fb-muted', 'آماده‌ی ارسال');
        row.appendChild(top); row.appendChild(it.bar); row.appendChild(it.status);
        if (file.size > MAX_BYTES) { fail(it, 'حجم بیشتر از ۲۵ مگابایت است.'); it.tooBig = true; }
        items.push(it); list.appendChild(row);
      });
      refresh();
    }
    input.addEventListener('change', function () { addFiles(input.files); input.value = ''; });
    ['dragenter', 'dragover'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('bg-base-300'); }); });
    ['dragleave', 'drop'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('bg-base-300'); }); });
    drop.addEventListener('drop', function (e) { addFiles(e.dataTransfer.files); });
    clear.addEventListener('click', function () { if (busy) return; items = []; list.textContent = ''; refresh(); });
    window.addEventListener('beforeunload', function (e) { if (busy) { e.preventDefault(); e.returnValue = ''; } });

    // خروجی: تعداد فایل‌هایی که ارسال نشدند
    function uploadAll(url) {
      return new Promise(function (resolve) {
        var queue = items.filter(function (i) { return i.state === 'ready' || (i.state === 'error' && !i.tooBig); });
        var idx = 0, active = 0;
        busy = true;
        function end() { busy = false; resolve(items.filter(function (i) { return i.state === 'error'; }).length); }
        function next() {
          while (active < 2 && idx < queue.length) start(queue[idx++]);
          if (!active && idx >= queue.length) end();
        }
        function start(it) {
          var cut = null;
          if (cfg.cuts) {
            cut = clean(it.cut.value);
            if (!/^\d+$/.test(cut) || +cut < 1 || +cut > 999) { fail(it, 'تعداد برش باید عددی بین ۱ تا ۹۹۹ باشد.'); return; }
          }
          active++; it.state = 'sending'; it.rm.disabled = true; it.status.className = 'text-xs fb-muted';
          var fd = new FormData(); fd.append('file', it.file, it.file.name);
          if (cut) fd.append('cut_count', cut);
          send(url, fd, null, function (p) { it.bar.value = p; it.status.textContent = p < 100 ? fa(p) + '٪' : 'در حال ثبت...'; }).then(function (res) {
            active--;
            if (res.ok) { it.state = 'done'; it.bar.value = 100; it.status.textContent = 'ارسال شد'; it.status.className = 'text-xs text-success'; }
            else { fail(it, res.error || 'ارسال انجام نشد.'); it.rm.disabled = false; }
            next();
          });
        }
        next();
      });
    }

    if (go) go.addEventListener('click', function () {
      go.disabled = true; note.classList.add('hidden');
      uploadAll(cfg.url).then(function (failed) {
        go.disabled = false;
        if (failed) { note.classList.remove('hidden'); return; }
        if (cfg.anchor) window.location.hash = cfg.anchor;
        window.location.reload();
      });
    });

    root._dropzone = {
      hasFiles: function () { return items.some(function (i) { return i.state !== 'done'; }); },
      uploadAll: uploadAll
    };
  }

  function initAll() { document.querySelectorAll('[data-dropzone]').forEach(function (r) { if (!r._dropzone) dropzone(r); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll); else initAll();
  document.body && document.body.addEventListener('htmx:afterSwap', initAll);

  // فرمی که فایل را بعد از ثبت می‌فرستد: <form data-deferred-upload> با <div data-upload-error class="hidden alert alert-soft alert-error">
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form.hasAttribute || !form.hasAttribute('data-deferred-upload')) return;
    var zone = form.querySelector('[data-dropzone]'), dz = zone && zone._dropzone;
    if (!dz || !dz.hasFiles()) return;   // بدون فایل: ارسال معمولی
    e.preventDefault();
    var err = form.querySelector('[data-upload-error]');
    function reset() { form.querySelectorAll('button[type=submit]').forEach(function (b) { b.disabled = false; var s = b.querySelector('.loading'); if (s) s.remove(); }); }
    function show(msg, projectUrl, retry) {
      err.textContent = msg; err.classList.remove('hidden');
      if (retry) {
        var r = el('button', 'btn btn-soft btn-sm', 'تلاش دوباره'); r.type = 'button'; r.addEventListener('click', retry);
        var a = el('a', 'btn btn-ghost btn-sm', 'رفتن به پروژه'); a.href = projectUrl;
        err.appendChild(r); err.appendChild(a);
      }
    }
    err.classList.add('hidden');
    send(form.action, new FormData(form)).then(function (res) {
      if (!res.ok) { show(res.error || 'ثبت انجام نشد.'); reset(); return; }
      function run() {
        err.classList.add('hidden');
        dz.uploadAll(res.upload_url).then(function (failed) {
          if (!failed) { window.location.href = res.redirect; return; }
          show('پروژه ثبت شد، ولی ارسال ' + fa(failed) + ' فایل انجام نشد.', res.project_url, run);
        });
      }
      run();
    });
  });
})();
