(function () {
  function say(node, text) {
    if (!node) return;
    node.textContent = text || '';
    node.classList.toggle('hidden', !text);
  }

  // بعد از بارگذاری فایل صفحه تازه می‌شود؛ متن ذخیره‌نشده نباید گم شود.
  var area = document.getElementById('catalog-description');
  if (area) {
    var key = 'catalog-draft:' + window.location.pathname;
    var note = document.querySelector('[data-draft-note]');
    try {
      var saved = window.sessionStorage.getItem(key);
      if (saved !== null) {
        if (saved.trim() === area.value.trim()) {
          window.sessionStorage.removeItem(key);
        } else {
          area.value = saved;
          if (note) note.classList.remove('hidden');
        }
      }
    } catch (err) {}
    area.addEventListener('input', function () {
      try { window.sessionStorage.setItem(key, area.value); } catch (err) {}
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-insert]') : null;
    if (!btn || !area) return;
    var text = btn.dataset.insert;
    var start = area.selectionStart == null ? area.value.length : area.selectionStart;
    var end = area.selectionEnd == null ? start : area.selectionEnd;
    area.value = area.value.slice(0, start) + '\n' + text + '\n' + area.value.slice(end);
    var pos = start + text.length + 2;
    area.focus();
    area.setSelectionRange(pos, pos);
    area.dispatchEvent(new Event('input', { bubbles: true }));
  });

  var coverErr = document.querySelector('[data-cover-error]');
  function coverRequest(url, fd, control) {
    say(coverErr, '');
    control.disabled = true;
    window.fbSend(url, fd, window.FB_CSRF).then(function (res) {
      control.disabled = false;
      if (res.ok) { window.location.reload(); return; }
      say(coverErr, res.error || 'انجام نشد.');
    });
  }
  var coverInput = document.querySelector('[data-cover-input]');
  if (coverInput) {
    coverInput.addEventListener('change', function () {
      var file = coverInput.files[0];
      if (!file) return;
      var fd = new FormData();
      fd.append('file', file, file.name);
      coverRequest(coverInput.dataset.url, fd, coverInput);
    });
  }
  var coverRemove = document.querySelector('[data-cover-remove]');
  if (coverRemove) {
    coverRemove.addEventListener('click', function () {
      if (!window.confirm('عکس شاخص حذف شود؟')) return;
      var fd = new FormData();
      fd.append('remove', '1');
      coverRequest(coverRemove.dataset.url, fd, coverRemove);
    });
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest ? e.target.closest('[data-media-delete]') : null;
    if (!btn) return;
    if (!window.confirm('این فایل حذف شود؟ اگر در متن آمده باشد، از متن هم برداشته می‌شود.')) return;
    btn.disabled = true;
    window.fbSend(btn.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
      if (res.ok) { window.location.reload(); return; }
      btn.disabled = false;
      window.alert(res.error || 'حذف نشد.');
    });
  });
})();
