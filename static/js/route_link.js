(function () {
  var NUM = /^-?\d{1,3}(\.\d+)?$/;

  function say(btn, text) {
    var box = btn.parentElement ? btn.parentElement.querySelector('[data-route-msg]') : null;
    if (!box) return;
    box.textContent = text || '';
    box.classList.toggle('hidden', !text);
  }
  function messageFor(err) {
    if (err && err.code === 1) return 'اجازه‌ی دسترسی به موقعیت داده نشد؛ نقطه‌ی پروژه روی نقشه باز می‌شود.';
    if (err && err.code === 3) return 'گرفتن موقعیت بیش از حد طول کشید؛ نقطه‌ی پروژه روی نقشه باز می‌شود.';
    return 'موقعیت شما پیدا نشد؛ نقطه‌ی پروژه روی نقشه باز می‌شود.';
  }
  // اگر مرورگر پنجره‌ی تازه را مسدود کرد، همین صفحه به لینک می‌رود
  function openLink(url) {
    var w = window.open(url, '_blank');
    if (w) {
      try { w.opener = null; } catch (err) {}
    } else {
      window.location.href = url;
    }
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-route]') : null;
    if (!btn) return;
    var dlat = btn.dataset.destLat, dlng = btn.dataset.destLng;
    if (!NUM.test(dlat || '') || !NUM.test(dlng || '')) return;
    say(btn, '');
    function fallback(text) {
      say(btn, text);
      openLink(btn.dataset.markUrl);
    }
    if (!navigator.geolocation) {
      fallback('این مرورگر موقعیت‌یابی را پشتیبانی نمی‌کند؛ نقطه‌ی پروژه روی نقشه باز می‌شود.');
      return;
    }
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function (pos) {
      btn.disabled = false;
      var url = btn.dataset.routeTpl
        .replace('{olat}', pos.coords.latitude.toFixed(6))
        .replace('{olng}', pos.coords.longitude.toFixed(6))
        .replace('{dlat}', dlat)
        .replace('{dlng}', dlng);
      openLink(url);
    }, function (err) {
      btn.disabled = false;
      fallback(messageFor(err));
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  });
})();
