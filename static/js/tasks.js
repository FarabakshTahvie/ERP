(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function say(card, msg) {
    var e = card.querySelector('[data-task-error]');
    if (!e) return;
    e.textContent = msg || '';
    e.classList.toggle('hidden', !msg);
  }
  function lock(card, on) {
    card.querySelectorAll('[data-task-check]').forEach(function (c) { c.disabled = on; });
  }
  function sync(card, res) {
    var checked = {};
    (res.checked || []).forEach(function (id) { checked[String(id)] = true; });
    card.querySelectorAll('[data-subtask-id]').forEach(function (cb) { cb.checked = !!checked[cb.dataset.subtaskId]; });
    var main = card.querySelector('[data-task-main-check]');
    if (main) main.checked = !!res.main_checked;
    var btn = card.querySelector('[data-task-submit-btn]');
    if (btn) btn.disabled = !res.main_checked;
    var prog = card.querySelector('[data-task-progress]');
    if (prog && res.total) prog.textContent = fa((res.checked || []).length) + ' از ' + fa(res.total);
  }

  document.addEventListener('change', function (ev) {
    var cb = ev.target.closest('[data-task-check]');
    if (!cb || !window.fbSend) return;
    var card = cb.closest('[data-task-card]');
    if (!card) return;
    var fd = new FormData(), before = !cb.checked;
    if (cb.dataset.subtaskId) fd.append('subtask_id', cb.dataset.subtaskId);
    fd.append('done', cb.checked ? '1' : '0');
    lock(card, true); say(card, '');
    window.fbSend(card.dataset.checkUrl, fd, window.FB_CSRF).then(function (res) {
      lock(card, false);
      if (res.ok) { sync(card, res); return; }
      cb.checked = before;
      say(card, res.error || 'ثبت تیک انجام نشد.');
    });
  });

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('[data-task-submit-action]');
    if (!btn || !window.fbSend) return;
    ev.preventDefault();
    var card = btn.closest('[data-task-card]');
    if (!card) return;
    var note = card.querySelector('[data-task-note-input]');
    var fd = new FormData();
    fd.append('note', note ? note.value : '');
    btn.disabled = true; say(card, '');
    window.fbSend(card.dataset.submitUrl, fd, window.FB_CSRF).then(function (res) {
      if (res.ok) { window.location.reload(); return; }
      btn.disabled = false;
      say(card, res.error || 'ثبت نهایی انجام نشد.');
    });
  });
})();