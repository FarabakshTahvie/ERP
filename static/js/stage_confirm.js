(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var dlg = document.querySelector('[data-stage-confirm]');
  var pendingForm = null;

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function block(title) {
    var box = el('div', 'flex flex-col gap-1.5');
    box.appendChild(el('div', 'fb-label', title));
    return box;
  }
  function line(name, value, valueCls) {
    var row = el('div', 'fb-inset flex items-center justify-between gap-2 text-xs');
    row.appendChild(el('span', 'min-w-0 break-words', name));
    row.appendChild(el('span', valueCls || 'font-technical shrink-0', value));
    return row;
  }

  function usageBlock(stage) {
    var box = stage.querySelector('[data-usage-box]');
    if (!box) return null;
    var out = block('مصرف این مرحله');
    var any = false;
    box.querySelectorAll('[data-usage-row]').forEach(function (row) {
      var input = row.querySelector('[data-usage-qty]');
      var value = input ? input.value.trim() : '';
      if (!value) return;
      any = true;
      out.appendChild(line(row.dataset.name, fa(value) + ' ' + row.dataset.unit));
      if (row.dataset.short) {
        out.appendChild(el('p', 'text-xs text-warning',
          'موجودی انبار کم بود؛ ' + fa(row.dataset.short) + ' ' + row.dataset.unit + ' از این مصرف از انبار کم نشد.'));
      }
    });
    if (!any) out.appendChild(el('p', 'text-xs text-warning', 'مصرفی نوشته نشده است. اگر چیزی مصرف شده برگردید و ثبت کنید.'));
    return out;
  }

  function installBlock(stage) {
    var box = stage.querySelector('[data-install-box]');
    if (!box) return null;
    var rows = box.querySelectorAll('[data-install-row]');
    var done = box.querySelectorAll('[data-install-check]:checked').length;
    var out = block('خدمت‌های نصب');
    out.appendChild(el('p', 'text-xs fb-muted', fa(done) + ' از ' + fa(rows.length) + ' خدمت انجام شده'));
    rows.forEach(function (row) {
      var ok = row.querySelector('[data-install-check]').checked;
      out.appendChild(line(row.dataset.name, ok ? 'انجام شد' : 'انجام نشده',
        'fb-badge shrink-0 ' + (ok ? 'fb-badge-success' : 'fb-badge-neutral')));
    });
    return out;
  }

  function cutsBlock(stage) {
    var box = stage.querySelector('[data-cuts-box]');
    if (!box) return null;
    var rows = box.querySelectorAll('[data-group-row]');
    var done = box.querySelectorAll('[data-group-cut]:checked').length;
    var out = block('گروه‌های برش');
    out.appendChild(el('p', 'text-xs fb-muted', fa(done) + ' از ' + fa(rows.length) + ' گروه انجام شده'));
    rows.forEach(function (row) {
      var ok = row.querySelector('[data-group-cut]').checked;
      out.appendChild(line(row.dataset.title, ok ? 'انجام شد' : 'انجام نشده',
        'fb-badge shrink-0 ' + (ok ? 'fb-badge-success' : 'fb-badge-neutral')));
    });
    return out;
  }

  function noteBlock(form) {
    var ta = form.querySelector('[data-complete-comment]');
    var text = ta ? ta.value.trim() : '';
    var voice = form.querySelector('input[name="voice"]');
    var hasVoice = !!(voice && voice.files && voice.files.length);
    if (!text && !hasVoice) return null;
    var out = block('توضیح مرحله');
    if (text) out.appendChild(el('p', 'fb-inset text-xs whitespace-pre-line', text.length > 300 ? text.slice(0, 300) + '…' : text));
    if (hasVoice) out.appendChild(el('p', 'text-xs', 'یک پیام صوتی هم ثبت می‌شود.'));
    return out;
  }

  function fill(form) {
    var stage = form.closest('[id^="stage-"]');
    var title = stage ? stage.querySelector('[data-stage-title]') : null;
    dlg.querySelector('[data-confirm-title]').textContent = 'تکمیل مرحله: ' + (title ? title.textContent.trim() : '');
    var body = dlg.querySelector('[data-confirm-body]');
    body.textContent = '';
    if (!stage) return;
    [usageBlock(stage), installBlock(stage), cutsBlock(stage), noteBlock(form)].forEach(function (b) {
      if (b) body.appendChild(b);
    });
  }

  // بعد از شنونده‌ی ذخیره‌های در راه (stage_usage.js) و آپلود فایل‌ها (اسکریپت صفحه) ثبت می‌شود.
  // _confirmed در همان بار آخرِ ارسال مصرف می‌شود؛ اگر آپلود شکست بخورد، بار بعد دوباره می‌پرسد.
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!dlg || e.defaultPrevented || !form.hasAttribute || !form.hasAttribute('data-confirm-report')) return;
    if (form._confirmed) { form._confirmed = false; return; }
    e.preventDefault();
    pendingForm = form;
    fill(form);
    dlg.showModal();
  });

  if (dlg) {
    dlg.querySelector('[data-confirm-back]').addEventListener('click', function () {
      pendingForm = null;
      dlg.close();
    });
    dlg.querySelector('[data-confirm-ok]').addEventListener('click', function () {
      var form = pendingForm;
      pendingForm = null;
      dlg.close();
      if (!form) return;
      form._confirmed = true;
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  }
})();
