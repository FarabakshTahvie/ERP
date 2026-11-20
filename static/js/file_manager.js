(function () {
  var dlg = document.getElementById('file-delete-dialog');
  var pageError = document.querySelector('[data-file-error]');

  function say(node, text) {
    if (!node) return;
    node.textContent = text || '';
    node.classList.toggle('hidden', !text);
  }

  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-file-visibility],[data-file-delete],[data-file-delete-ok]') : null;
    if (!t) return;

    if (t.hasAttribute('data-file-visibility')) {
      say(pageError, '');
      t.disabled = true;
      var fd = new FormData();
      fd.append('public', t.dataset.next);
      window.fbSend(t.dataset.url, fd, window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        t.disabled = false;
        say(pageError, res.error || 'تغییر انجام نشد.');
      });
    } else if (t.hasAttribute('data-file-delete')) {
      if (!dlg) return;
      dlg.querySelector('[data-file-delete-label]').textContent = t.dataset.label;
      say(dlg.querySelector('[data-file-delete-error]'), '');
      var ok = dlg.querySelector('[data-file-delete-ok]');
      ok.dataset.url = t.dataset.url;
      ok.disabled = false;
      dlg.showModal();
    } else if (t.hasAttribute('data-file-delete-ok') && t.dataset.url) {
      var err = dlg.querySelector('[data-file-delete-error]');
      say(err, '');
      t.disabled = true;
      window.fbSend(t.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
        if (res.ok) { window.location.reload(); return; }
        t.disabled = false;
        say(err, res.error || 'حذف نشد.');
      });
    }
  });
})();
