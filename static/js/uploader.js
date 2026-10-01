(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function clean(s) { return String(s || '').replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); }).replace(/[٠-٩]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.indexOf(d); }).trim(); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sizeText(b) { return b >= 1048576 ? fa((b / 1048576).toFixed(1)) + ' مگابایت' : fa(Math.max(1, Math.round(b / 1024))) + ' کیلوبایت'; }
  var MAX_BYTES = 25 * 1024 * 1024;

  // یک درخواست XHR با گزارش پیشرفت؛ همیشه resolve می‌شود با {ok, ...}
  function send(url, formData, csrf, onProgress) {
    return new Promise(function (resolve) {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.setRequestHeader('X-CSRFToken', csrf);
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.upload.onprogress = function (e) { if (e.lengthComputable && onProgress) onProgress(Math.round(e.loaded / e.total * 100)); };
      xhr.onload = function () {
        if (xhr.status === 413) return resolve({ ok: false, error: 'حجم فایل یا مجموع فایل‌ها بیش از سقف مجاز سرور (۲۵ مگابایت) است.' });
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (err) {}
        resolve(data || { ok: false, error: 'پاسخ نامعتبر از سرور (کد ' + fa(xhr.status) + ').' });
      };
      xhr.onerror = function () { resolve({ ok: false, error: 'اتصال قطع شد؛ دوباره تلاش کنید.' }); };
      xhr.send(formData);
    });
  }
  window.fbSend = send;

  // ارسال کل یک فرم (ثبت پروژه) با نوار پیشرفت. ui: {wrap, bar, text, onError(msg)}
  window.fbSubmitWithProgress = function (form, ui) {
    var total = 0;
    Array.prototype.forEach.call(form.querySelectorAll('input[type=file]'), function (i) {
      Array.prototype.forEach.call(i.files, function (f) { total += f.size; });
    });
    if (total > 24 * 1024 * 1024) {
      ui.onError('مجموع حجم فایل‌ها بیشتر از ۲۴ مگابایت است؛ فایل‌های کمتری انتخاب کنید یا بعد از ثبت پروژه، از داخل مرحله بفرستید.');
      return Promise.resolve();
    }
    ui.wrap.classList.remove('hidden'); ui.bar.value = 0;
    var token = form.querySelector('[name=csrfmiddlewaretoken]').value;
    return send(form.action, new FormData(form), token, function (p) {
      ui.bar.value = p;
      ui.text.textContent = p < 100 ? 'در حال ارسال فایل‌ها: ' + fa(p) + '٪' : 'در حال ثبت پروژه...';
    }).then(function (res) {
      if (res.ok && res.redirect) { window.location.href = res.redirect; return; }
      ui.wrap.classList.add('hidden');
      ui.onError(res.error || 'ثبت انجام نشد.');
    });
  };

  // پنل درگ‌ودراپ مرحله. cfg: {mount, url, csrf, withCuts, anchor}
  window.fbUploadPanel = function (cfg) {
    var items = [], uploading = false;
    var drop = el('div', 'fb-inset flex flex-col items-center gap-2 text-center py-5 border border-dashed border-base-300');
    drop.appendChild(el('span', 'text-sm', 'فایل‌ها را اینجا رها کنید یا انتخاب کنید'));
    var input = el('input', 'sr-only'); input.type = 'file'; input.multiple = true; input.setAttribute('aria-label', 'انتخاب فایل');
    var pick = el('button', 'btn btn-soft btn-sm', 'انتخاب فایل'); pick.type = 'button';
    pick.addEventListener('click', function () { input.click(); });
    drop.appendChild(pick); drop.appendChild(input);
    var list = el('div', 'flex flex-col gap-2');
    var actions = el('div', 'flex gap-2 hidden');
    var go = el('button', 'btn btn-primary btn-sm', 'ارسال فایل‌ها'); go.type = 'button';
    var clear = el('button', 'btn btn-ghost btn-sm', 'پاک‌کردن فهرست'); clear.type = 'button';
    actions.appendChild(go); actions.appendChild(clear);
    var note = el('p', 'fb-hint hidden', 'برخی فایل‌ها ارسال نشد. موارد موفق ثبت شده‌اند؛ صفحه را تازه کنید تا در فهرست ببینید.');
    [drop, list, actions, note].forEach(function (n) { cfg.mount.appendChild(n); });

    function refresh() { actions.classList.toggle('hidden', !items.length); }
    function addFiles(files) {
      Array.prototype.forEach.call(files, function (file) {
        var row = el('div', 'fb-inset flex flex-col gap-1.5');
        var top = el('div', 'flex items-center gap-2');
        var name = el('span', 'text-xs flex-1 min-w-0 break-all', file.name); name.dir = 'auto';   // نام عیناً همان است
        top.appendChild(name);
        top.appendChild(el('span', 'text-xs fb-muted shrink-0', sizeText(file.size)));
        var it = { file: file, state: 'ready', row: row };
        if (cfg.withCuts) {
          it.cut = el('input', 'input input-sm w-16 font-technical'); it.cut.type = 'text'; it.cut.value = '1';
          it.cut.setAttribute('inputmode', 'numeric'); it.cut.dir = 'ltr'; it.cut.setAttribute('aria-label', 'تعداد برش');
          top.appendChild(el('span', 'text-xs fb-muted shrink-0', 'برش:')); top.appendChild(it.cut);
        }
        it.rm = el('button', 'btn btn-ghost btn-xs', 'حذف'); it.rm.type = 'button';
        it.rm.addEventListener('click', function () { if (uploading) return; row.remove(); items.splice(items.indexOf(it), 1); refresh(); });
        top.appendChild(it.rm);
        it.bar = el('progress', 'progress progress-primary w-full'); it.bar.max = 100; it.bar.value = 0;
        it.status = el('span', 'text-xs fb-muted', 'آماده‌ی ارسال');
        row.appendChild(top); row.appendChild(it.bar); row.appendChild(it.status);
        if (file.size > MAX_BYTES) { it.state = 'error'; it.status.textContent = 'حجم بیشتر از ۲۵ مگابایت است؛ ارسال نمی‌شود.'; it.status.className = 'text-xs text-error'; it.tooBig = true; }
        items.push(it); list.appendChild(row);
      });
      refresh();
    }
    input.addEventListener('change', function () { addFiles(input.files); input.value = ''; });
    ['dragenter', 'dragover'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add('bg-base-300'); }); });
    ['dragleave', 'drop'].forEach(function (t) { drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.remove('bg-base-300'); }); });
    drop.addEventListener('drop', function (e) { addFiles(e.dataTransfer.files); });
    clear.addEventListener('click', function () { if (uploading) return; items = []; list.textContent = ''; refresh(); });
    window.addEventListener('beforeunload', function (e) { if (uploading) { e.preventDefault(); e.returnValue = ''; } });

    function fail(it, msg) { it.state = 'error'; it.status.textContent = msg; it.status.className = 'text-xs text-error'; }
    go.addEventListener('click', function () {
      var queue = items.filter(function (i) { return i.state === 'ready' || (i.state === 'error' && !i.tooBig); });
      if (!queue.length) return;
      uploading = true; go.disabled = true;
      var idx = 0, active = 0, LIMIT = 2;
      function finish() {
        uploading = false; go.disabled = false;
        var failed = items.some(function (i) { return i.state === 'error'; });
        if (!failed) { var u = location.pathname + location.search; location.href = u + '#' + (cfg.anchor || ''); location.reload(); }
        else note.classList.remove('hidden');
      }
      function next() {
        while (active < LIMIT && idx < queue.length) start(queue[idx++]);
        if (active === 0 && idx >= queue.length) finish();
      }
      function start(it) {
        var cut = null;
        if (cfg.withCuts) {
          cut = clean(it.cut.value);
          if (!/^\d+$/.test(cut) || +cut < 1 || +cut > 999) { fail(it, 'تعداد برش باید عددی بین ۱ تا ۹۹۹ باشد.'); return; }
        }
        active++; it.state = 'sending'; it.rm.disabled = true; it.status.className = 'text-xs fb-muted';
        var fd = new FormData(); fd.append('file', it.file, it.file.name);
        if (cut) fd.append('cut_count', cut);
        send(cfg.url, fd, cfg.csrf, function (p) {
          it.bar.value = p; it.status.textContent = p < 100 ? fa(p) + '٪' : 'در حال ثبت...';
        }).then(function (res) {
          active--;
          if (res.ok) { it.state = 'done'; it.bar.value = 100; it.status.textContent = 'ارسال شد'; it.status.className = 'text-xs text-success'; }
          else { fail(it, res.error || 'ارسال انجام نشد.'); it.rm.disabled = false; }
          next();
        });
      }
      next();
    });
  };
})();
