(function () {
  function say(text) {
    var box = document.querySelector('[data-loc-error]');
    if (!box) return;
    box.textContent = text || '';
    box.classList.toggle('hidden', !text);
  }
  function messageFor(err) {
    if (err && err.code === 1) return 'اجازه‌ی دسترسی به موقعیت داده نشد؛ در تنظیمات مرورگر اجازه بدهید یا روی نقشه کلیک کنید.';
    if (err && err.code === 3) return 'گرفتن موقعیت بیش از حد طول کشید؛ دوباره تلاش کنید.';
    return 'موقعیت شما پیدا نشد؛ روی نقشه کلیک کنید.';
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-my-location]') : null;
    if (!btn) return;
    say('');
    if (!navigator.geolocation) {
      say('این مرورگر موقعیت‌یابی را پشتیبانی نمی‌کند؛ روی نقشه کلیک کنید.');
      return;
    }
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function (pos) {
      btn.disabled = false;
      var lat = pos.coords.latitude, lng = pos.coords.longitude;
      var latEl = document.getElementById('id_latitude'), lngEl = document.getElementById('id_longitude');
      if (latEl) latEl.value = lat.toFixed(6);
      if (lngEl) lngEl.value = lng.toFixed(6);
      var out = document.querySelector('[data-loc-readout]');
      if (out) out.textContent = lat.toFixed(6) + ', ' + lng.toFixed(6);
      if (window.fbLocationMap) window.fbLocationMap.set(lat, lng);
    }, function (err) {
      btn.disabled = false;
      say(messageFor(err));
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });
})();
