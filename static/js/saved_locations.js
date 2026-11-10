(function () {
  var dlg = document.getElementById('location-dialog');
  if (!dlg) return;
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  var DEFAULT = { lat: 36.2979, lng: 59.6062 };
  var SDK = 'https://static.neshan.org/sdk/maplibre/5.24.3/neshan-maplibre-sdk';
  var STYLE = 'https://static.neshan.org/sdk/maplibre/styles/light.json';
  var form = dlg.querySelector('[data-location-form]');
  function q(sel) { return dlg.querySelector(sel); }
  var els = {
    heading: q('[data-form-title]'), error: q('[data-form-error]'), submit: q('[data-form-submit]'),
    candBox: q('[data-candidate-box]'), candText: q('[data-candidate-text]'), confText: q('[data-confirmed-text]'),
    removeBox: q('[data-remove-image-box]'), manLat: q('#loc-manual-lat'), manLng: q('#loc-manual-lng'),
    title: form.querySelector('[name="title"]'), description: form.querySelector('[name="description"]'),
    lat: form.querySelector('[name="latitude"]'), lng: form.querySelector('[name="longitude"]')
  };
  var state = { action: '', confirmed: null, candidate: null, map: null, gl: null, markers: {}, sdk: null };

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function fmt(pt) { return pt.lat.toFixed(6) + ', ' + pt.lng.toFixed(6); }
  function say(text) { els.error.textContent = text || ''; els.error.classList.toggle('hidden', !text); }

  function paintCandidate() {
    els.candBox.classList.toggle('hidden', !state.candidate);
    els.candText.textContent = state.candidate ? fmt(state.candidate) : '';
  }
  function paintConfirmed() {
    els.confText.textContent = state.confirmed ? fmt(state.confirmed) : '—';
    els.lat.value = state.confirmed ? state.confirmed.lat.toFixed(6) : '';
    els.lng.value = state.confirmed ? state.confirmed.lng.toFixed(6) : '';
  }

  // ---------- نقشه (فقط وقتی کلید نشان هست) ----------
  function loadSdk() {
    if (state.sdk) return state.sdk;
    state.sdk = new Promise(function (resolve, reject) {
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = SDK + '.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = SDK + '.umd.js';
      s.onload = function () { resolve((window.maplibregl && window.maplibregl.default) || window.maplibregl); };
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return state.sdk;
  }
  function syncMarkers() {
    if (!state.map) return;
    [['confirmed', state.confirmed, {}], ['candidate', state.candidate, { color: '#B45309' }]].forEach(function (m) {
      if (state.markers[m[0]]) { state.markers[m[0]].remove(); state.markers[m[0]] = null; }
      if (m[1]) state.markers[m[0]] = new state.gl.Marker(m[2]).setLngLat([m[1].lng, m[1].lat]).addTo(state.map);
    });
  }
  function ensureMap() {
    var box = document.getElementById('location-map');
    if (!box || !dlg.dataset.mapKey) return Promise.resolve(null);
    if (state.map) return Promise.resolve(state.map);
    return loadSdk().then(function (gl) {
      state.gl = gl;
      state.map = new gl.Map({ container: box, style: STYLE, center: [DEFAULT.lng, DEFAULT.lat], zoom: 12, apiKey: dlg.dataset.mapKey });
      state.map.addControl(new gl.NavigationControl());
      state.map.on('click', function (e) { setCandidate(e.lngLat.lat, e.lngLat.lng, false); });   // فقط پیشنهاد؛ ثبت نمی‌شود
      return state.map;
    }, function () { say('نقشه بارگذاری نشد؛ مختصات را دستی بنویسید.'); return null; });
  }

  // ---------- نقطه‌ی پیشنهادی ← تایید ----------
  function setCandidate(lat, lng, fly) {
    state.candidate = { lat: lat, lng: lng };
    els.manLat.value = lat.toFixed(6);
    els.manLng.value = lng.toFixed(6);
    paintCandidate();
    syncMarkers();
    if (fly && state.map) state.map.flyTo({ center: [lng, lat], zoom: 16 });
  }
  q('[data-candidate-confirm]').addEventListener('click', function () {
    if (!state.candidate) return;
    state.confirmed = state.candidate;
    state.candidate = null;
    say('');
    paintCandidate();
    paintConfirmed();
    syncMarkers();
  });
  q('[data-candidate-cancel]').addEventListener('click', function () {
    state.candidate = null;
    paintCandidate();
    syncMarkers();
  });
  q('[data-manual-apply]').addEventListener('click', function () {
    var lat = parseFloat(els.manLat.value), lng = parseFloat(els.manLng.value);
    if (isNaN(lat) || isNaN(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      say('مختصات را درست بنویسید: عرض بین ۹۰- تا ۹۰ و طول بین ۱۸۰- تا ۱۸۰.');
      return;
    }
    say('');
    setCandidate(lat, lng, true);
  });
  q('[data-my-location]').addEventListener('click', function () {
    var btn = this;
    if (!navigator.geolocation) { say('این مرورگر موقعیت‌یابی را پشتیبانی نمی‌کند؛ روی نقشه بزنید یا مختصات را بنویسید.'); return; }
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function (pos) {
      btn.disabled = false;
      say('');
      setCandidate(pos.coords.latitude, pos.coords.longitude, true);
    }, function () {
      btn.disabled = false;
      say('موقعیت شما پیدا نشد؛ اجازه‌ی مرورگر را بررسی کنید یا روی نقشه بزنید.');
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });

  // ---------- باز کردن فرم ----------
  function openForm(o) {
    form.reset();
    state.action = o.url;
    els.heading.textContent = o.heading;
    els.title.value = o.title || '';
    els.description.value = o.description || '';
    els.removeBox.classList.toggle('hidden', !o.hasImage);
    els.manLat.value = '';
    els.manLng.value = '';
    state.candidate = null;
    state.confirmed = (o.lat && o.lng) ? { lat: parseFloat(o.lat), lng: parseFloat(o.lng) } : null;
    paintCandidate();
    paintConfirmed();
    say('');
    els.submit.disabled = false;
    els.submit.textContent = 'ثبت';
    dlg.showModal();
    ensureMap().then(function (map) {
      if (!map) return;
      map.resize();
      var c = state.confirmed || DEFAULT;
      map.jumpTo({ center: [c.lng, c.lat], zoom: state.confirmed ? 15 : 12 });
      syncMarkers();
    });
  }
  q('[data-form-cancel]').addEventListener('click', function () { dlg.close(); });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    if (state.candidate) { say('نقطه‌ی پیشنهادی هنوز تایید نشده؛ «تایید این نقطه» یا «انصراف» را بزنید.'); return; }
    if (!state.confirmed) { say('ابتدا یک نقطه را روی نقشه انتخاب و تایید کنید.'); return; }
    if (!els.title.value.trim()) { say('عنوان را بنویسید.'); return; }
    say('');
    els.submit.disabled = true;
    window.fbSend(state.action, new FormData(form), window.FB_CSRF, function (p) {
      els.submit.textContent = p < 100 ? fa(p) + '٪' : 'در حال ثبت...';
    }).then(function (res) {
      if (res.ok) { window.location.reload(); return; }
      els.submit.disabled = false;
      els.submit.textContent = 'ثبت';
      say(res.error || 'ثبت نشد.');
    });
  });

  // ---------- دکمه‌های صفحه (تفویضی) ----------
  var delDlg = document.getElementById('location-delete-dialog');
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-location-add],[data-location-edit],[data-location-delete],[data-delete-ok]') : null;
    if (!t) return;
    if (t.hasAttribute('data-location-add')) {
      openForm({ url: t.dataset.url, heading: 'موقعیت جدید' });
    } else if (t.hasAttribute('data-location-edit')) {
      var d = t.dataset;
      openForm({ url: d.url, heading: 'ویرایش موقعیت', title: d.title, description: d.description,
                 lat: d.lat, lng: d.lng, hasImage: d.hasImage === '1' });
    } else if (t.hasAttribute('data-location-delete')) {
      delDlg.querySelector('[data-delete-label]').textContent = t.dataset.label;
      delDlg.querySelector('[data-delete-error]').classList.add('hidden');
      var okBtn = delDlg.querySelector('[data-delete-ok]');
      okBtn.dataset.url = t.dataset.url;
      okBtn.disabled = false;
      delDlg.showModal();
    } else if (t.hasAttribute('data-delete-ok') && t.dataset.url) {
      var err = delDlg.querySelector('[data-delete-error]');
      t.disabled = true;
      window.fbSend(t.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        t.disabled = false;
        err.textContent = res.error || 'حذف نشد.';
        err.classList.remove('hidden');
      });
    }
  });
})();
