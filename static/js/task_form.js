(function () {
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function readJson(id) {
    var n = document.getElementById(id);
    try { return n ? JSON.parse(n.textContent || '[]') : []; } catch (e) { return []; }
  }

  function initSubtasks(form) {
    var mount = form.querySelector('[data-subtasks-mount]'), hidden = form.querySelector('[data-subtasks-hidden]');
    if (!mount || !hidden || !window.fbLineEditor) return;
    window.fbLineEditor({
      mount: mount, hidden: hidden, addLabel: 'افزودن زیروظیفه', emptyText: 'زیروظیفه‌ای ثبت نشده.',
      initial: readJson('task-subtasks-initial'),
      columns: [{ key: 'title', type: 'text', label: '', placeholder: 'عنوان زیروظیفه', cls: 'flex-1 min-w-48' }]
    });
  }

  function initAssignees(form) {
    var chips = form.querySelector('[data-assignee-chips]'), select = form.querySelector('[data-assignee-select]');
    var err = form.querySelector('[data-assignee-error]');
    if (!chips || !select) return;
    function has(id) { return !!chips.querySelector('input[value="' + id + '"]'); }
    function add(id, name) {
      if (!id || has(id)) return;
      var chip = el('span', 'fb-badge fb-badge-neutral gap-1');
      chip.appendChild(document.createTextNode(name));
      var input = el('input'); input.type = 'hidden'; input.name = 'assignee_ids'; input.setAttribute('value', id);
      chip.appendChild(input);
      var rm = el('button', 'btn btn-ghost btn-xs btn-circle', '×');
      rm.type = 'button'; rm.setAttribute('aria-label', 'حذف ' + name);
      rm.addEventListener('click', function () { chip.remove(); });
      chip.appendChild(rm);
      chips.appendChild(chip);
      if (err) err.classList.add('hidden');
    }
    readJson('task-assignees-initial').forEach(function (a) { add(String(a.id), a.name); });
    form.querySelector('[data-assignee-add]').addEventListener('click', function () {
      var opt = select.options[select.selectedIndex];
      if (opt && opt.value) add(opt.value, opt.dataset.name || opt.text);
      select.value = '';
    });
    form.querySelector('[data-assignee-all]').addEventListener('click', function () {
      Array.prototype.forEach.call(select.options, function (o) { if (o.value) add(o.value, o.dataset.name || o.text); });
    });
    form.addEventListener('submit', function (e) {
      if (!chips.querySelector('input')) {
        e.preventDefault();
        if (err) err.classList.remove('hidden');
      }
    });
  }

  function initAttachments(form) {
    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-attachment-delete]');
      if (!b || !window.fbSend) return;
      if (!window.confirm('این پیوست حذف شود؟')) return;
      b.disabled = true;
      window.fbSend(b.dataset.url, new FormData(), window.FB_CSRF).then(function (res) {
        if (res.ok) { var row = b.closest('[data-attachment]'); if (row) row.remove(); }
        else { b.disabled = false; window.alert(res.error || 'حذف انجام نشد.'); }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-task-form]').forEach(function (f) { initSubtasks(f); initAssignees(f); initAttachments(f); });
  });
})();