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

  // ---------- پخش‌کننده (Media Chrome خودمیزبان: static/js/vendor/media-chrome.js) ----------
  // آن فایل قبل از این فایل لود می‌شود؛ اگر لود نشد، پخش‌کننده‌ی خود مرورگر می‌آید.
  function hasPlayer() {
    return !!(window.customElements && window.customElements.get('media-controller'));
  }
  function tag(name, attrs) {
    var e = document.createElement(name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }
  // اعداد زمان (داخل shadowRoot خود کتابخانه) فارسی می‌شوند؛ فقط متن عوض می‌شود
  function persianDigits(el) {
    function convert(root) {
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), node;
      while ((node = walker.nextNode())) {
        if (/[0-9]/.test(node.nodeValue)) node.nodeValue = M.fa(node.nodeValue);
      }
    }
    [el.shadowRoot, el].forEach(function (root) {
      if (!root) return;
      convert(root);
      new MutationObserver(function () { convert(root); })
        .observe(root, { childList: true, characterData: true, subtree: true });
    });
  }
  function faTag(name, attrs) {
    var e = tag(name, attrs);
    persianDigits(e);
    return e;
  }

  // شکل موج قابل‌کلیک و کشیدن؛ مستقیم روی خود عنصر صوت کار می‌کند
  function waveSeek(a, f) {
    var wave = M.el('div', 'msgr-wave');
    wave.setAttribute('role', 'slider');
    wave.setAttribute('tabindex', '0');
    wave.setAttribute('aria-label', 'جابه‌جایی در پیام صوتی');
    wave.setAttribute('aria-valuemin', '0');
    var bars = f.peaks.map(function (p) {
      var b = M.el('span', 'msgr-wave-bar');
      b.style.height = Math.max(12, Math.min(100, p)) + '%';
      wave.appendChild(b);
      return b;
    });
    function total() { return isFinite(a.duration) && a.duration > 0 ? a.duration : (f.dur || 0); }
    function paintWave() {
      var t = total(), r = t ? Math.min(1, a.currentTime / t) : 0, lit = Math.round(r * bars.length);
      bars.forEach(function (b, i) { b.classList.toggle('msgr-wave-on', i < lit); });
      wave.setAttribute('aria-valuemax', String(Math.round(t)));
      wave.setAttribute('aria-valuenow', String(Math.round(a.currentTime)));
    }
    function seekTo(e) {
      var t = total();
      if (!t) return;
      var rect = wave.getBoundingClientRect();
      a.currentTime = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)) * t;
      paintWave();
    }
    var drag = false;
    wave.addEventListener('pointerdown', function (e) {
      drag = true;
      try { wave.setPointerCapture(e.pointerId); } catch (err) {}
      seekTo(e);
    });
    wave.addEventListener('pointermove', function (e) { if (drag) seekTo(e); });
    ['pointerup', 'pointercancel'].forEach(function (ev) { wave.addEventListener(ev, function () { drag = false; }); });
    wave.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var t = total();
      if (t) { a.currentTime = Math.min(t, Math.max(0, a.currentTime + (e.key === 'ArrowRight' ? 5 : -5))); paintWave(); }
    });
    ['timeupdate', 'seeked', 'loadedmetadata', 'durationchange', 'ended'].forEach(function (ev) {
      a.addEventListener(ev, paintWave);
    });
    paintWave();
    return wave;
  }

  function videoPlayer(f) {
    var v = M.el('video');
    v.preload = 'metadata'; v.playsInline = true; v.src = f.url;
    if (f.thumb) v.poster = f.thumb;
    if (!hasPlayer()) {
      v.className = 'w-full max-h-72 rounded-field bg-black';
      v.controls = true;
      return v;
    }
    v.setAttribute('slot', 'media');
    var ctl = tag('media-controller', { nohotkeys: '' });
    ctl.className = 'msgr-player msgr-player-video';
    if (f.w && f.h) ctl.style.aspectRatio = Math.min(1.78, Math.max(0.7, f.w / f.h)).toFixed(3);
    ctl.appendChild(v);
    ctl.appendChild(tag('media-loading-indicator', { slot: 'centered-chrome' }));
    var bar = tag('media-control-bar');
    bar.appendChild(tag('media-play-button'));
    bar.appendChild(tag('media-time-range'));
    bar.appendChild(faTag('media-time-display', { showduration: '' }));
    bar.appendChild(tag('media-mute-button'));
    bar.appendChild(tag('media-fullscreen-button'));
    ctl.appendChild(bar);
    return ctl;
  }
  function audioPlayer(f) {
    var a = M.el('audio');
    a.preload = 'metadata'; a.src = f.url;
    if (!hasPlayer()) {
      a.className = 'w-full h-10';
      a.controls = true;
      return a;
    }
    a.setAttribute('slot', 'media');
    var ctl = tag('media-controller', { audio: '', nohotkeys: '' });
    ctl.className = 'msgr-player';
    ctl.appendChild(a);
    var bar = tag('media-control-bar');
    bar.appendChild(tag('media-play-button'));
    if (f.peaks && f.peaks.length >= 8) {
      bar.appendChild(waveSeek(a, f));
      bar.appendChild(faTag('media-time-display', { showduration: '', class: 'msgr-time' }));
    } else {
      bar.appendChild(faTag('media-time-display'));
      bar.appendChild(tag('media-time-range'));
      bar.appendChild(faTag('media-duration-display'));
    }
    ctl.appendChild(bar);
    return ctl;
  }

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
        box.appendChild(videoPlayer(f));
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
        wrap.appendChild(audioPlayer(f));
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

  // هم‌زمان فقط یک صوت یا ویدیو پخش شود (رویداد play حباب نمی‌شود، پس با capture می‌گیریم)
  root.addEventListener('play', function (e) {
    var t = e.target;
    if (!t || (t.tagName !== 'AUDIO' && t.tagName !== 'VIDEO')) return;
    root.querySelectorAll('audio, video').forEach(function (m) { if (m !== t && !m.paused) m.pause(); });
  }, true);

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

  // عکس شاخص ویدیو: یک فریم نزدیک ابتدا، حداکثر ۴۸۰ پیکسل. شکست یا فریم سیاه = بدون عکس (ارسال مختل نمی‌شود)
  function videoPoster(file) {
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file), v = document.createElement('video'), done = false, timer;
      function finish(result) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        v.removeAttribute('src');
        v.load();
        URL.revokeObjectURL(url);
        resolve(result);
      }
      timer = setTimeout(function () { finish(null); }, 8000);
      v.muted = true; v.playsInline = true; v.preload = 'metadata';
      v.onerror = function () { finish(null); };
      v.onloadedmetadata = function () {
        var d = isFinite(v.duration) ? v.duration : 0;
        v.currentTime = d > 0 ? Math.min(1, d / 10) : 0.1;
      };
      v.onseeked = function () {
        try {
          var w = v.videoWidth, h = v.videoHeight;
          if (!w || !h) return finish(null);
          var probe = document.createElement('canvas'), pg, i;
          probe.width = probe.height = 8;
          pg = probe.getContext('2d');
          pg.drawImage(v, 0, 0, 8, 8);
          var px = pg.getImageData(0, 0, 8, 8).data, sum = 0;
          for (i = 0; i < px.length; i += 4) sum += px[i] + px[i + 1] + px[i + 2];
          if (sum / 192 < 6) return finish(null);
          var k = Math.min(1, 480 / Math.max(w, h)), c = document.createElement('canvas');
          c.width = Math.round(w * k); c.height = Math.round(h * k);
          c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
          c.toBlob(function (b) { finish(b ? { blob: b, w: w, h: h } : null); }, 'image/jpeg', 0.8);
        } catch (e) { finish(null); }
      };
      v.src = url;
    });
  }

  var PEAK_BARS = 32, PEAK_MAX_BYTES = 5 * 1024 * 1024;

  // شکل موج: میانگین دامنه در ۳۲ بازه (۰ تا ۱۰۰). فایل بزرگ یا ناپشتیبانی‌شده = بدون شکل موج
  function audioPeaks(file) {
    var Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    if (!Ctx || !file.arrayBuffer || file.size > PEAK_MAX_BYTES) return Promise.resolve(null);
    return file.arrayBuffer().then(function (buf) {
      var ctx;
      try { ctx = new Ctx(1, 1, 16000); } catch (e) { ctx = new Ctx(1, 1, 44100); }
      return new Promise(function (resolve, reject) {
        var timer = setTimeout(reject, 10000);
        var ok = function (x) { clearTimeout(timer); resolve(x); };
        var fail = function (e) { clearTimeout(timer); reject(e); };
        var p = ctx.decodeAudioData(buf, ok, fail);
        if (p && p.catch) p.catch(fail);
      });
    }).then(function (audio) {
      var chans = [], c, i, j;
      for (c = 0; c < audio.numberOfChannels; c++) chans.push(audio.getChannelData(c));
      var len = audio.length, per = Math.floor(len / PEAK_BARS), out = [], max = 0;
      if (per < 64) return null;
      for (i = 0; i < PEAK_BARS; i++) {
        var from = i * per, to = i === PEAK_BARS - 1 ? len : from + per, sum = 0, n = 0;
        for (j = from; j < to; j += 4) {
          for (c = 0; c < chans.length; c++) { sum += Math.abs(chans[c][j]); n++; }
        }
        var avg = n ? sum / n : 0;
        out.push(avg);
        if (avg > max) max = avg;
      }
      if (!max) return null;
      return out.map(function (v) { return Math.round(Math.pow(v / max, 0.6) * 100); });
    }).catch(function () { return null; });
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
    if (it.poster) { fd.append('poster', it.poster.blob, 'poster.jpg'); fd.append('width', String(it.poster.w)); fd.append('height', String(it.poster.h)); }
    if (it.peaks) fd.append('peaks', it.peaks.join(','));
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
      var extra = it.kind === 'video' ? videoPoster(f) : (it.kind === 'audio' ? audioPeaks(f) : Promise.resolve(null));
      extra.then(function (x) {
        if (it.removed) return;
        if (it.kind === 'video') it.poster = x; else if (it.kind === 'audio') it.peaks = x;
        it.state = 'ready'; paint(it); pump();
      });
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
