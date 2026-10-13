(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹', MAX_REC = 300, PEAK_BARS = 32, PEAK_MAX_BYTES = 5 * 1024 * 1024;

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function tag(name, attrs) {
    var e = document.createElement(name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }
  function icon(sprite, name, cls) {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', cls || 'w-4 h-4');
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', sprite + '#' + name);
    svg.appendChild(use);
    return svg;
  }
  function hasPlayer() {
    return !!(window.customElements && window.customElements.get('media-controller'));
  }
  function persianDigits(node) {
    function convert(root) {
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), n;
      while ((n = walker.nextNode())) {
        if (/[0-9]/.test(n.nodeValue)) n.nodeValue = fa(n.nodeValue);
      }
    }
    [node.shadowRoot, node].forEach(function (root) {
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
  function parsePeaks(s) {
    var v = String(s || '').split(',').map(function (x) { return parseInt(x, 10); })
      .filter(function (x) { return !isNaN(x); });
    return v.length >= 8 ? v : null;
  }

  // ---------- پخش‌کننده و موج (کپی از پیام‌رسان؛ پیام‌رسان دست نخورده) ----------
  function waveSeek(a, peaks, dur) {
    var wave = el('div', 'msgr-wave');
    wave.setAttribute('role', 'slider');
    wave.setAttribute('tabindex', '0');
    wave.setAttribute('aria-label', 'جابه‌جایی در پیام صوتی');
    wave.setAttribute('aria-valuemin', '0');
    var bars = peaks.map(function (p) {
      var b = el('span', 'msgr-wave-bar');
      b.style.height = Math.max(12, Math.min(100, p)) + '%';
      wave.appendChild(b);
      return b;
    });
    function total() { return isFinite(a.duration) && a.duration > 0 ? a.duration : (dur || 0); }
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

  function audioPlayer(src, peaks, dur) {
    var a = el('audio');
    a.preload = 'metadata';
    a.src = src;
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
    if (peaks && peaks.length >= 8) {
      bar.appendChild(waveSeek(a, peaks, dur));
      bar.appendChild(faTag('media-time-display', { showduration: '', class: 'msgr-time' }));
    } else {
      bar.appendChild(faTag('media-time-display'));
      bar.appendChild(tag('media-time-range'));
      bar.appendChild(faTag('media-duration-display'));
    }
    ctl.appendChild(bar);
    return ctl;
  }

  // شکل موج: میانگین دامنه در ۳۲ بازه (۰ تا ۱۰۰)؛ ناموفق = null
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

  // هم‌زمان فقط یک صدا پخش شود
  document.addEventListener('play', function (e) {
    var t = e.target;
    if (!t || t.tagName !== 'AUDIO') return;
    document.querySelectorAll('audio').forEach(function (m) { if (m !== t && !m.paused) m.pause(); });
  }, true);

  // ---------- نمایش پیام‌های ثبت‌شده ----------
  function hydratePlayers() {
    document.querySelectorAll('[data-voice-player]').forEach(function (n) {
      if (n._voiceDone) return;
      n._voiceDone = true;
      n.appendChild(audioPlayer(n.dataset.src, parsePeaks(n.dataset.peaks), parseInt(n.dataset.dur, 10) || 0));
    });
  }

  // ---------- ضبط ----------
  function pickMime() {
    var c = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'];
    for (var i = 0; i < c.length; i++) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c[i])) return c[i];
    }
    return '';
  }
  function extFor(mime) { return /mp4/.test(mime) ? 'm4a' : /ogg/.test(mime) ? 'ogg' : 'webm'; }

  function initRecorder(root) {
    if (root._voiceDone) return;
    root._voiceDone = true;
    var form = root.closest('form');
    var ta = form && form.querySelector('[data-complete-comment]');
    if (!form || !ta) return;
    if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder)) return;
    var sprite = root.dataset.sprite || '';
    var st = { r: null, pending: null, file: null, url: null, inputs: [] };

    var box = el('div', 'flex flex-col gap-2');
    var idle = el('div');
    var recBtn = el('button', 'btn btn-soft btn-sm gap-1 self-start');
    recBtn.type = 'button';
    recBtn.appendChild(icon(sprite, 'mic', 'w-4 h-4'));
    recBtn.appendChild(el('span', null, 'ضبط پیام صوتی'));
    idle.appendChild(recBtn);

    var rec = el('div', 'hidden');
    var recRow = el('div', 'fb-inset flex items-center gap-2');
    recRow.appendChild(el('span', 'inline-block w-2.5 h-2.5 rounded-full bg-error animate-pulse'));
    var timeEl = el('span', 'font-technical text-sm', fa('0:00'));
    recRow.appendChild(timeEl);
    recRow.appendChild(el('span', 'flex-1 min-w-0 text-xs fb-muted', 'در حال ضبط؛ حداکثر ۵ دقیقه'));
    var stopBtn = el('button', 'btn btn-soft btn-error btn-sm gap-1');
    stopBtn.type = 'button';
    stopBtn.appendChild(icon(sprite, 'square', 'w-4 h-4'));
    stopBtn.appendChild(el('span', null, 'توقف'));
    var cancelBtn = el('button', 'btn btn-ghost btn-sm', 'لغو');
    cancelBtn.type = 'button';
    recRow.appendChild(stopBtn);
    recRow.appendChild(cancelBtn);
    rec.appendChild(recRow);

    var ready = el('div', 'hidden');
    var readyRow = el('div', 'fb-inset flex flex-col gap-2');
    var holder = el('div');
    var delBtn = el('button', 'btn btn-ghost btn-sm gap-1 self-start');
    delBtn.type = 'button';
    delBtn.appendChild(icon(sprite, 'trash-2', 'w-4 h-4'));
    delBtn.appendChild(el('span', null, 'حذف و ضبط دوباره'));
    readyRow.appendChild(holder);
    readyRow.appendChild(delBtn);
    ready.appendChild(readyRow);

    var msg = el('p', 'text-xs fb-muted hidden');
    [idle, rec, ready, msg].forEach(function (n) { box.appendChild(n); });
    root.appendChild(box);

    function say(t, bad) {
      msg.textContent = t || '';
      msg.className = 'text-xs ' + (bad ? 'text-error' : 'fb-muted') + (t ? '' : ' hidden');
    }
    function show(which) {
      idle.classList.toggle('hidden', which !== 'idle');
      rec.classList.toggle('hidden', which !== 'rec');
      ready.classList.toggle('hidden', which !== 'ready');
    }
    function syncRequired() { ta.required = !st.file; }

    function clearVoice() {
      st.pending = null;
      st.inputs.forEach(function (n) { n.remove(); });
      st.inputs = [];
      if (st.url) URL.revokeObjectURL(st.url);
      st.url = null; st.file = null;
      holder.textContent = '';
      syncRequired();
      show('idle');
    }

    function hidden(name, value) {
      var i = el('input');
      i.type = 'hidden'; i.name = name; i.value = value;
      form.appendChild(i);
      st.inputs.push(i);
    }
    function attach(file, secs, peaks) {
      var fi = el('input', 'hidden');
      fi.type = 'file'; fi.name = 'voice';
      try {
        var dt = new DataTransfer();
        dt.items.add(file);
        fi.files = dt.files;
      } catch (e) { return false; }
      form.appendChild(fi);
      st.inputs.push(fi);
      hidden('voice_duration', String(secs));
      hidden('voice_peaks', peaks ? peaks.join(',') : '');
      return true;
    }

    function stopRec(cancel) {
      var r = st.r;
      if (!r) return;
      st.r = null;
      r.cancel = cancel;
      clearInterval(r.timer);
      if (r.mr.state !== 'inactive') r.mr.stop();
      r.stream.getTracks().forEach(function (t) { t.stop(); });
      if (cancel) show('idle');
    }

    function startRec() {
      if (st.file || st.r || st.pending) return;
      say('');
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        var mime = pickMime(), chunks = [];
        var mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        var r = { mr: mr, stream: stream, t0: Date.now(), cancel: false, auto: false, timer: null };
        mr.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
        mr.onstop = function () {
          if (r.cancel) return;
          var secs = Math.min(MAX_REC, Math.round((Date.now() - r.t0) / 1000));
          if (secs < 1 || !chunks.length) { show('idle'); return; }
          var type = mr.mimeType || mime || 'audio/webm';
          var file = new File([new Blob(chunks, { type: type })], 'voice.' + extFor(type), { type: type });
          st.pending = r;
          holder.textContent = '';
          holder.appendChild(el('span', 'loading loading-spinner loading-sm'));
          show('ready');
          audioPeaks(file).then(function (peaks) {
            if (st.pending !== r) return;
            st.pending = null;
            if (!attach(file, secs, peaks)) {
              clearVoice();
              say('ثبت پیام صوتی در این مرورگر ممکن نیست؛ توضیح را بنویسید.', true);
              return;
            }
            st.file = file;
            st.url = URL.createObjectURL(file);
            holder.textContent = '';
            holder.appendChild(audioPlayer(st.url, peaks, secs));
            syncRequired();
            if (r.auto) say('به سقف ۵ دقیقه رسید؛ ضبط متوقف شد و پیام صوتی آماده‌ی ثبت است.');
          });
        };
        r.timer = setInterval(function () {
          var s = Math.floor((Date.now() - r.t0) / 1000);
          timeEl.textContent = fa(Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2));
          if (s >= MAX_REC) { r.auto = true; stopRec(false); }
        }, 250);
        st.r = r;
        mr.start();
        timeEl.textContent = fa('0:00');
        show('rec');
      }).catch(function () {
        say('دسترسی به میکروفون ممکن نشد؛ اجازه‌ی مرورگر را بررسی کنید.', true);
      });
    }

    recBtn.addEventListener('click', startRec);
    stopBtn.addEventListener('click', function () { stopRec(false); });
    cancelBtn.addEventListener('click', function () { stopRec(true); });
    delBtn.addEventListener('click', clearVoice);
    form.addEventListener('submit', function (e) {
      if (st.r || st.pending) { e.preventDefault(); say('ابتدا ضبط را متوقف کنید و چند لحظه صبر کنید.', true); }
    });
    window.addEventListener('pagehide', function () { stopRec(true); });
    syncRequired();
  }

  function init() {
    document.querySelectorAll('[data-voice-recorder]').forEach(initRecorder);
    hydratePlayers();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
