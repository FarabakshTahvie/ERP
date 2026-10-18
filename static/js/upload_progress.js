(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var MAX_TOTAL = 25 * 1024 * 1024;   // هم‌سقف nginx
  var SHOW_AFTER_MS = 350;            // ارسال سریع، پنجره‌ی لحظه‌ای نشان نمی‌دهد
  var busy = false;                   // هشدار ترک صفحه وسط ارسال
  var resetLast = null;               // برگشت با دکمه‌ی back

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function sizeText(b) {
    if (b >= 1048576) return fa((b / 1048576).toFixed(1)).replace('.', '٫') + ' مگابایت';
    return fa(Math.max(1, Math.round(b / 1024))) + ' کیلوبایت';
  }
  function filesOf(form) {
    var out = [];
    Array.prototype.forEach.call(form.querySelectorAll('input[type=file]'), function (input) {
      if (input.disabled || !input.files) return;
      Array.prototype.forEach.call(input.files, function (f) { out.push(f); });
    });
    return out;
  }
  function failText(status) {
    if (status === 413) return 'حجم فایل‌ها بیشتر از ۲۵ مگابایت است.';
    if (status === 403) return 'اجازه‌ی این کار را ندارید یا نشست شما تمام شده؛ صفحه را تازه کنید.';
    if (status >= 500) return 'خطای سرور؛ چند لحظه بعد دوباره تلاش کنید.';
    return 'ارسال انجام نشد (کد ' + fa(status) + ').';
  }

  // پنجره‌ی پیشرفت؛ on = {cancel, retry, closed}
  function makeOverlay(summary, on) {
    var dlg = el('dialog', 'modal');
    dlg.setAttribute('aria-label', 'پیشرفت ارسال فایل');
    var box = el('div', 'modal-box max-w-sm flex flex-col gap-3');
    var titleEl = el('h3', 'font-bold text-base', 'در حال ارسال');
    var whatEl = el('p', 'text-xs fb-muted break-all', summary);
    whatEl.dir = 'auto';
    var barEl = el('progress', 'progress progress-primary w-full');
    barEl.max = 100;
    barEl.value = 0;
    barEl.setAttribute('aria-label', 'پیشرفت ارسال');
    var statusEl = el('p', 'text-xs fb-muted', '');
    statusEl.setAttribute('aria-live', 'polite');
    var hintEl = el('p', 'fb-hint', 'تا پایان ارسال این صفحه را نبندید.');
    var errEl = el('p', 'fb-error hidden', '');
    errEl.setAttribute('role', 'alert');
    var actions = el('div', 'modal-action');
    var cancelBtn = el('button', 'btn btn-ghost btn-sm', 'انصراف');
    var retryBtn = el('button', 'btn btn-soft btn-sm hidden', 'تلاش دوباره');
    var closeBtn = el('button', 'btn btn-ghost btn-sm hidden', 'بستن');
    [cancelBtn, retryBtn, closeBtn].forEach(function (b) { b.type = 'button'; actions.appendChild(b); });
    [titleEl, whatEl, barEl, statusEl, hintEl, errEl, actions].forEach(function (n) { box.appendChild(n); });
    dlg.appendChild(box);

    var state = 'up';          // up | wait | failed
    var shown = false;
    var disposing = false;
    var ui;

    dlg.addEventListener('cancel', function (e) { if (state !== 'failed') e.preventDefault(); });
    dlg.addEventListener('close', function () {
      if (state !== 'failed' && !disposing) { dlg.showModal(); return; }   // بسته‌شدن ناخواسته (مثلاً دو بار Esc)
      shown = false;
      disposing = false;
      if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
      on.closed();
    });
    cancelBtn.addEventListener('click', on.cancel);
    retryBtn.addEventListener('click', on.retry);
    closeBtn.addEventListener('click', function () { dlg.close(); });

    ui = {
      open: function () {
        if (shown) return;
        shown = true;
        document.body.appendChild(dlg);
        dlg.showModal();
      },
      progress: function (loaded, total) {
        if (!total) return;
        var pct = Math.min(100, Math.round(loaded / total * 100));
        barEl.value = pct;
        statusEl.textContent = fa(pct) + '٪ — ' + sizeText(loaded) + ' از ' + sizeText(total);
      },
      wait: function () {
        state = 'wait';
        cancelBtn.classList.add('hidden');
        barEl.removeAttribute('value');
        statusEl.textContent = 'ارسال شد؛ در حال ثبت...';
      },
      fail: function (msg, canRetry) {
        ui.open();
        state = 'failed';
        titleEl.textContent = 'ارسال نشد';
        barEl.classList.add('hidden');
        statusEl.classList.add('hidden');
        hintEl.classList.add('hidden');
        errEl.textContent = msg;
        errEl.classList.remove('hidden');
        cancelBtn.classList.add('hidden');
        retryBtn.classList.toggle('hidden', !canRetry);
        closeBtn.classList.remove('hidden');
      },
      again: function () {
        state = 'up';
        titleEl.textContent = 'در حال ارسال';
        barEl.classList.remove('hidden');
        barEl.max = 100;
        barEl.value = 0;
        statusEl.classList.remove('hidden');
        statusEl.textContent = '';
        hintEl.classList.remove('hidden');
        errEl.classList.add('hidden');
        retryBtn.classList.add('hidden');
        closeBtn.classList.add('hidden');
        cancelBtn.classList.remove('hidden');
      },
      dispose: function () {
        if (shown && dlg.open) { disposing = true; dlg.close(); }
      }
    };
    return ui;
  }

  function start(form, submitter, files, total) {
    var url = form.getAttribute('action') || window.location.href;   // فرم بدون action یعنی همین صفحه (مثل ارسال معمولی)
    var data;
    try { data = new FormData(form, submitter || undefined); } catch (err) { data = new FormData(form); }
    if (submitter && submitter.name && !data.has(submitter.name)) data.append(submitter.name, submitter.value);
    var buttons = form.querySelectorAll('button[type=submit]');
    var summary = files.length === 1 ? files[0].name + ' — ' + sizeText(total)
                                     : fa(files.length) + ' فایل — ' + sizeText(total);
    var xhr = null;
    var timer = null;
    var ui = null;

    function lock(on) {
      form._fbBusy = on;
      Array.prototype.forEach.call(buttons, function (b) { b.disabled = on; });
    }
    function finish() {
      clearTimeout(timer);
      busy = false;
      resetLast = null;
      lock(false);
    }
    function send() {
      busy = true;
      ui.again();
      xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.setRequestHeader('X-CSRFToken', window.FB_CSRF || '');
      xhr.setRequestHeader('X-FB-Upload', '1');   // عمداً X-Requested-With نمی‌فرستیم؛ ویوها همان رفتار فرم معمولی را دارند
      xhr.upload.onprogress = function (ev) { if (ev.lengthComputable) ui.progress(ev.loaded, ev.total); };
      xhr.upload.onload = function () { ui.wait(); };
      xhr.onload = function () {
        clearTimeout(timer);
        busy = false;
        if (xhr.status >= 200 && xhr.status < 400) {
          window.location.assign(xhr.responseURL || window.location.href);   // XHR ریدایرکت را دنبال کرده؛ آدرس نهایی را عادی باز می‌کنیم
          return;
        }
        ui.fail(failText(xhr.status), true);
      };
      xhr.onerror = function () {
        clearTimeout(timer);
        busy = false;
        ui.fail('اتصال قطع شد؛ دوباره تلاش کنید.', true);
      };
      timer = setTimeout(ui.open, SHOW_AFTER_MS);
      xhr.send(data);
    }

    ui = makeOverlay(summary, {
      cancel: function () { if (xhr) xhr.abort(); ui.dispose(); },
      retry: send,
      closed: finish
    });
    lock(true);
    resetLast = function () { ui.dispose(); finish(); };
    if (total > MAX_TOTAL) { ui.fail('حجم فایل‌ها بیشتر از ۲۵ مگابایت است.', false); return; }
    send();
  }

  // روی window ثبت می‌شود تا بعد از همه‌ی شنونده‌های دیگر (تکمیل مرحله، فرم خرید و ...) اجرا شود و اگر کسی preventDefault زده کاری نکند
  window.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || !form || !form.hasAttribute || !form.hasAttribute('data-upload-progress')) return;
    if ((form.getAttribute('method') || '').toLowerCase() !== 'post') return;
    // مرورگر قدیمی که دکمه‌ی ارسال‌کننده را نمی‌گوید: دکمه‌ی نام‌دار (مثل «تایید»/«رد») گم می‌شود؛ ارسال معمولی
    if (e.submitter === undefined &&
        form.querySelector('button[name]:not([type=button]):not([type=reset]), input[type=submit][name]')) return;
    var files = filesOf(form);
    var total = files.reduce(function (sum, f) { return sum + f.size; }, 0);
    if (!total) return;                 // بدون فایل ← ارسال معمولی
    e.preventDefault();
    if (form._fbBusy) return;           // دوبار کلیک
    start(form, e.submitter || null, files, total);
  });

  window.addEventListener('beforeunload', function (e) {
    if (!busy) return;
    e.preventDefault();
    e.returnValue = '';
  });
  window.addEventListener('pageshow', function (e) {
    if (e.persisted && resetLast) resetLast();
  });
})();