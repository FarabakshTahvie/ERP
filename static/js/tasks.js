(function () {
  document.addEventListener('change', function (ev) {
    var checkbox = ev.target.closest('[data-task-check]');
    if (!checkbox) return;

    var taskId = checkbox.dataset.taskId;
    var subtaskId = checkbox.dataset.subtaskId || '';
    var done = checkbox.checked ? '1' : '0';
    var url = '/tasks/' + taskId + '/check/';

    checkbox.disabled = true;

    var fd = new FormData();
    if (subtaskId) {
      fd.append('subtask_id', subtaskId);
    }
    fd.append('done', done);

    window.fbSend(url, fd, window.FB_CSRF)
      .then(function (res) {
        checkbox.disabled = false;
        if (!res.ok) {
          checkbox.checked = !checkbox.checked;
          alert(res.error || 'خطا در ثبت تیک');
          return;
        }
        // همگام‌سازی وضعیت در صورت نیاز
        var card = checkbox.closest('.collapse');
        if (card) {
          // به‌روزرسانی پیشرفت یا چک‌باکس اصلی
          var mainCheck = card.querySelector('[data-task-main-check]');
          if (mainCheck) {
            mainCheck.checked = res.main_checked;
          }
          // فعال/غیرفعال کردن دکمه ثبت
          var submitBtn = card.querySelector('[data-task-submit-btn]');
          if (submitBtn) {
            submitBtn.disabled = !res.main_checked;
          }
        }
      })
      .catch(function () {
        checkbox.disabled = false;
        checkbox.checked = !checkbox.checked;
        alert('خطای شبکه');
      });
  });

  document.addEventListener('click', function (ev) {
    var btn = ev.target.closest('[data-task-submit-action]');
    if (!btn) return;
    ev.preventDefault();

    var taskId = btn.dataset.taskId;
    var card = btn.closest('.collapse');
    var noteInput = card ? card.querySelector('[data-task-note-input]') : null;
    var note = noteInput ? noteInput.value : '';
    var url = '/tasks/' + taskId + '/submit/';

    var fd = new FormData();
    fd.append('note', note);

    btn.disabled = true;
    window.fbSend(url, fd, window.FB_CSRF)
      .then(function (res) {
        if (!res.ok) {
          btn.disabled = false;
          alert(res.error || 'خطا در ثبت نهایی');
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        btn.disabled = false;
        alert('خطای شبکه');
      });
  });
})();
