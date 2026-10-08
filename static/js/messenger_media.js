(function () {
  var M = window.fbMsgr, root = document.querySelector('[data-msgr-chat]');
  if (!M || !root) return;

  // ---------- نمایش پیوست‌ها (فقط createElement و textContent) ----------
  var LABELS = { image: 'عکس', video: 'ویدیو', audio: 'فایل صوتی', voice: 'پیام صوتی', file: 'فایل' };
  M.fileLabel = function (files) {
    if (!files || !files.length) return '';
    return files.length > 1 ? 'آلبوم' : (LABELS[files[0].kind] || 'فایل');
  };
  M.snippetOf = function (m) { return (m.text || M.fileLabel(m.files)).slice(0, 80); };
  M.size = function (b) {
    return b >= 1048576 ? M.fa((b / 1048576).toFixed(1)) + ' مگابایت' : M.fa(Math.max(1, Math.round(b / 1024))) + ' کیلوبایت';
  };

  M.openViewer = function (list, idx) {
    var dlg = document.querySelector('[data-msgr-viewer]');
    if (!dlg) return;
    var img = dlg.querySelector('[data-view-img]'), cnt = dlg.querySelector('[data-view-count]');
    var dl = dlg.querySelector('[data-view-dl]');
    var prev = dlg.querySelector('[data-view-prev]'), next = dlg.querySelector('[data-view-next]');
    var i = idx;
    function show(n) {
      i = (n + list.length) % list.length;
      img.src = list[i].url; img.alt = list[i].name;
      cnt.textContent = list.length > 1 ? M.fa(i + 1) + ' از ' + M.fa(list.length) : '';
      dl.href = list[i].url; dl.setAttribute('download', list[i].name);
      prev.classList.toggle('hidden', list.length < 2);
      next.classList.toggle('hidden', list.length < 2);
    }
    prev.onclick = function () { show(i - 1); };
    next.onclick = function () { show(i + 1); };
    dlg.onkeydown = function (e) {
      if (e.key === 'ArrowRight') show(i - 1);
      if (e.key === 'ArrowLeft') show(i + 1);
    };
    show(idx);
    dlg.showModal();
  };

  M.renderFiles = function (files) {
    var box = M.el('div', 'flex flex-col gap-1 mb-1 w-64 sm:w-72 max-w-full');
    var imgs = files.filter(function (f) { return f.kind === 'image'; });
    if (imgs.length) {
      var cols = imgs.length === 1 ? 'grid-cols-1' : (imgs.length === 2 || imgs.length === 4) ? 'grid-cols-2' : 'grid-cols-3';
      var grid = M.el('div', 'grid gap-0.5 overflow-hidden rounded-field ' + cols);
      imgs.forEach(function (f, i) {
        var b = M.el('button', 'block p-0 border-0 bg-transparent cursor-zoom-in');
        b.type = 'button';
        var im = M.el('img', imgs.length === 1 ? 'w-full max-h-72 object-cover' : 'w-full h-28 object-cover');
        im.src = f.thumb || f.url; im.alt = f.name; im.loading = 'lazy';
        if (imgs.length === 1 && f.w && f.h) im.style.aspectRatio = f.w + ' / ' + f.h;
        b.appendChild(im);
        b.addEventListener('click', function (e) { e.stopPropagation(); M.openViewer(imgs, i); });
        grid.appendChild(b);
      });
      box.appendChild(grid);
    }
    files.forEach(function (f) {
      if (f.kind === 'image') return;
      if (f.kind === 'video') {
        var v = M.el('video', 'w-full max-h-72 rounded-field bg-black');
        v.controls = true; v.preload = 'metadata'; v.playsInline = true; v.src = f.url;
        box.appendChild(v);
      } else if (f.kind === 'audio' || f.kind === 'voice') {
        var wrap = M.el('div', 'flex flex-col gap-0.5');
        if (f.kind === 'voice') {
          var cap = M.el('div', 'flex items-center gap-1 text-[10px] opacity-80');
          cap.appendChild(M.icon('mic', 'w-3 h-3'));
          cap.appendChild(M.el('span', null, 'پیام صوتی' + (f.dur ? ' · ' + M.fa(f.dur) + ' ثانیه' : '')));
          wrap.appendChild(cap);
        } else {
          var nm0 = M.el('div', 'text-[10px] opacity-80 truncate', f.name);
          nm0.dir = 'auto';
          wrap.appendChild(nm0);
        }
        var a = M.el('audio', 'w-full h-10');
        a.controls = true; a.preload = 'metadata'; a.src = f.url;
        wrap.appendChild(a);
        box.appendChild(wrap);
      } else {
        var d = M.el('a', 'flex items-center gap-2 rounded-field bg-base-100/20 px-2 py-1.5 no-underline');
        d.href = f.url; d.setAttribute('download', f.name);
        d.appendChild(M.icon('file-text', 'w-6 h-6 shrink-0'));
        var t = M.el('div', 'flex-1 min-w-0');
        var nm = M.el('div', 'text-xs font-semibold truncate', f.name);
        nm.dir = 'auto';
        t.appendChild(nm);
        t.appendChild(M.el('div', 'text-[10px] opacity-70', M.size(f.size)));
        d.appendChild(t);
        d.appendChild(M.icon('download', 'w-4 h-4 shrink-0'));
        box.appendChild(d);
      }
    });
    return box;
  };

  // ---------- سینی ارسال، آپلود و ضبط صدا ----------
  var ds = root.dataset;
  var MAX_FILES = 10, MAX_BYTES = 24 * 1024 * 1024, OPT_OVER = 2 * 1024 * 1024, MAX_REC = 300, PARALLEL = 2;
  var form = root.querySelector('[data-msgr-form]'), ta = form.querySelector('textarea');
  var tray = root.querySelector('[data-msgr-tray]'), list = tray.querySelector('[data-tray-list]');
  var input = form.querySelector('[data-msgr-file]'), clip = form.querySelector('[data-msgr-clip]');
  var mic = form.querySelector('[data-msgr-mic]');
  var recBar = root.querySelector('[data-msgr-rec]'), recTime = recBar.querySelector('[data-rec-time]');
  var errBox = root.querySelector('[data-msgr-error]'), errTimer = null;
  var items = [], rec = null, api = M.media = { autoSend: null };

  M.flash = function (msg) {
    errBox.textContent = msg || 'ثبت نشد.';
    errBox.classList.remove('hidden');
    clearTimeout(errTimer);
    errTimer = setTimeout(function () { errBox.classList.add('hidden'); }, 6000);
  };

  function kindOf(f) {
    var t = f.type || '';
    if (t.indexOf('image/') === 0 && t.indexOf('svg') === -1) return 'image';
    if (t.indexOf('video/') === 0) return 'video';
    if (t.indexOf('audio/') === 0) return 'audio';
    return 'file';
  }

  // عکس بالای ۲ مگابایت: حداکثر ۲۴۰۰ پیکسل و JPEG با کیفیت ۰٫۸۵ (بهینه‌سازی اصلی سمت سرور است)
  function shrink(file) {
    if (!/^image\/(jpeg|png|webp|bmp)$/.test(file.type) || file.size <= OPT_OVER) return Promise.resolve(file);
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        URL.revokeObjectURL(url);
        var k = Math.min(1, 2400 / Math.max(img.naturalWidth, img.naturalHeight));
        var c = document.createElement('canvas');
        c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
        var g = c.getContext('2d');
        g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
        g.drawImage(img, 0, 0, c.width, c.height);
        c.toBlob(function (b) {
          if (!b || b.size >= file.size) return resolve(file);
          resolve(new File([b], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' }));
        }, 'image/jpeg', 0.85);
      };
      img.onerror = function () { URL.revokeObjectURL(url); resolve(file); };
      img.src = url;
    });
  }

  function buildRow(it) {
    var row = M.el('div', 'fb-inset flex items-center gap-2');
    var thumb;
    if (it.kind === 'image') {
      thumb = M.el('img', 'w-10 h-10 object-cover rounded-field shrink-0 bg-base-300');
      thumb.alt = '';
      it.url = URL.createObjectURL(it.file);
      thumb.src = it.url;
    } else {
      thumb = M.el('div', 'w-10 h-10 rounded-field shrink-0 bg-base-300 flex items-center justify-center');
      thumb.appendChild(M.icon(it.voice ? 'mic' : 'file-text', 'w-5 h-5'));
    }
    var body = M.el('div', 'flex-1 min-w-0 flex flex-col gap-0.5');
    var nm = M.el('div', 'text-xs truncate', it.name);
    nm.dir = 'auto';
    it.bar = M.el('progress', 'progress progress-primary w-full');
    it.bar.max = 100; it.bar.value = 0;
    it.status = M.el('div', 'text-[10px] fb-muted');
    body.appendChild(nm); body.appendChild(it.bar); body.appendChild(it.status);
    it.retry = M.el('button', 'btn btn-ghost btn-xs gap-1 hidden');
    it.retry.type = 'button';
    it.retry.appendChild(M.icon('refresh-cw', 'w-3.5 h-3.5'));
    it.retry.appendChild(M.el('span', null, 'تلاش مجدد'));
    it.retry.addEventListener('click', function () { it.state = 'ready'; it.err = ''; paint(it); pump(); });
    var rm = M.el('button', 'btn btn-ghost btn-xs btn-circle');
    rm.type = 'button'; rm.setAttribute('aria-label', 'حذف از فهرست');
    rm.appendChild(M.icon('x', 'w-4 h-4'));
    rm.addEventListener('click', function () { removeItem(it); });
    row.appendChild(thumb); row.appendChild(body); row.appendChild(it.retry); row.appendChild(rm);
    return row;
  }

  function paint(it) {
    it.bar.value = it.pct;
    it.bar.classList.toggle('hidden', it.state === 'done' || it.state === 'error');
    var txt = { preparing: 'در حال آماده‌سازی...', ready: 'در صف ارسال', uploading: M.fa(it.pct) + '٪',
                done: 'آماده', error: it.err || 'ارسال نشد' }[it.state];
    it.status.textContent = txt;
    it.status.className = 'text-[10px] ' + (it.state === 'error' ? 'text-error' : it.state === 'done' ? 'text-success' : 'fb-muted');
    it.retry.classList.toggle('hidden', it.state !== 'error' || !!it.fatal);
  }

  function changed() { tray.classList.toggle('hidden', !items.length); }

  function removeItem(it) {
    it.removed = true;
    if (it.url) URL.revokeObjectURL(it.url);
    items.splice(items.indexOf(it), 1);
    it.el.remove();
    changed(); pump();
  }

  function pump() {
    var running = items.filter(function (i) { return i.state === 'uploading'; }).length;
    items.forEach(function (i) {
      if (i.state === 'ready' && running < PARALLEL) { running++; upload(i); }
    });
  }

  function upload(it) {
    it.state = 'uploading'; it.pct = 0; paint(it);
    var fd = new FormData();
    fd.append('file', it.file, it.file.name);
    if (it.voice) { fd.append('voice', '1'); fd.append('duration', String(it.dur || 1)); }
    window.fbSend(ds.uploadUrl, fd, window.FB_CSRF, function (p) { it.pct = p; paint(it); }).then(function (res) {
      if (it.removed) return;
      if (res.ok) { it.state = 'done'; it.attId = res.attachment.id; it.pct = 100; }
      else { it.state = 'error'; it.err = res.error || 'ارسال نشد'; }
      paint(it); pump();
      if (it.state === 'done' && it.autoSend && !api.busy() && !api.hasError() && api.autoSend) api.autoSend();
    });
  }

  function prepare(it) {
    shrink(it.file).then(function (f) {
      if (it.removed) return;
      it.file = f; it.size = f.size;
      if (f.size > MAX_BYTES) {
        it.state = 'error'; it.fatal = true; it.err = 'حجم فایل بیشتر از ۲۴ مگابایت است.';
        paint(it); return;
      }
      it.state = 'ready'; paint(it); pump();
    });
  }

  function add(file, extra) {
    if (items.length >= MAX_FILES) { M.flash('در هر پیام حداکثر ۱۰ فایل می‌توان فرستاد.'); return null; }
    var it = { file: file, kind: kindOf(file), state: 'preparing', pct: 0, size: file.size, name: file.name };
    Object.keys(extra || {}).forEach(function (k) { it[k] = extra[k]; });
    it.el = buildRow(it);
    list.appendChild(it.el);
    items.push(it);
    paint(it); changed();
    prepare(it);
    return it;
  }

  function addFiles(fl) { Array.prototype.forEach.call(fl, function (f) { add(f); }); }

  api.hasItems = function () { return items.length > 0; };
  api.busy = function () {
    return items.some(function (i) { return i.state === 'preparing' || i.state === 'ready' || i.state === 'uploading'; });
  };
  api.hasError = function () { return items.some(function (i) { return i.state === 'error'; }); };
  api.ids = function () { return items.map(function (i) { return i.attId; }); };
  api.clear = function () {
    items.forEach(function (i) { i.removed = true; if (i.url) URL.revokeObjectURL(i.url); });
    items = []; list.textContent = ''; changed();
  };

  clip.addEventListener('click', function () { input.click(); });
  input.addEventListener('change', function () { addFiles(input.files); input.value = ''; });
  ta.addEventListener('paste', function (e) {
    var fl = (e.clipboardData && e.clipboardData.files) || [];
    if (fl.length) { e.preventDefault(); addFiles(fl); }
  });
  root.addEventListener('dragover', function (e) {
    if (e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, 'Files') !== -1) e.preventDefault();
  });
  root.addEventListener('drop', function (e) {
    if (e.dataTransfer && e.dataTransfer.files.length) { e.preventDefault(); addFiles(e.dataTransfer.files); }
  });

  // ---------- ضبط پیام صوتی ----------
  var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (!canRecord) mic.classList.add('hidden');

  function pickMime() {
    var c = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'];
    for (var i = 0; i < c.length; i++) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c[i])) return c[i];
    }
    return '';
  }
  function extFor(mime) { return /mp4/.test(mime) ? 'm4a' : /ogg/.test(mime) ? 'ogg' : 'webm'; }

  function paintRec(on) {
    recBar.classList.toggle('hidden', !on);
    mic.textContent = '';
    mic.appendChild(M.icon(on ? 'square' : 'mic', 'w-5 h-5'));
    mic.classList.toggle('btn-ghost', !on);
    mic.classList.toggle('btn-soft', on);
    mic.classList.toggle('btn-error', on);
    if (on) recTime.textContent = M.fa('0:00');
  }

  function stopRec(cancel) {
    var r = rec;
    if (!r) return;
    rec = null;
    r.cancel = cancel;
    clearInterval(r.timer);
    if (r.mr.state !== 'inactive') r.mr.stop();
    r.stream.getTracks().forEach(function (t) { t.stop(); });
    paintRec(false);
  }

  function startRec() {
    if (api.hasItems() || ta.value.trim()) {
      M.flash('ابتدا متن یا فایل‌های آماده‌ی ارسال را بفرستید یا پاک کنید.');
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var mime = pickMime(), chunks = [];
      var mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      var r = { mr: mr, stream: stream, t0: Date.now(), cancel: false, timer: null };
      mr.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
      mr.onstop = function () {
        if (r.cancel) return;
        var secs = Math.round((Date.now() - r.t0) / 1000);
        if (secs < 1 || !chunks.length) return;
        var type = mr.mimeType || mime || 'audio/webm';
        var f = new File([new Blob(chunks, { type: type })], 'voice.' + extFor(type), { type: type });
        add(f, { voice: true, dur: secs, name: 'پیام صوتی', autoSend: true, kind: 'audio' });
      };
      r.timer = setInterval(function () {
        var s = Math.floor((Date.now() - r.t0) / 1000);
        recTime.textContent = M.fa(Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2));
        if (s >= MAX_REC) stopRec(false);
      }, 250);
      rec = r;
      mr.start();
      paintRec(true);
    }).catch(function () {
      M.flash('دسترسی به میکروفون ممکن نشد؛ اجازه‌ی مرورگر را بررسی کنید.');
    });
  }

  mic.addEventListener('click', function () { if (rec) stopRec(false); else startRec(); });
  recBar.querySelector('[data-rec-cancel]').addEventListener('click', function () { stopRec(true); });
  window.addEventListener('pagehide', function () { stopRec(true); });
})();
