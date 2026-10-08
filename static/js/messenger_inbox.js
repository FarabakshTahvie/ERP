(function () {
  var M = window.fbMsgr, root = document.querySelector('[data-msgr-root]');
  if (!M || !root) return;
  var list = root.querySelector('[data-msgr-list]'), search = root.querySelector('[data-msgr-search]');
  if (!list) return;
  var activeKey = root.dataset.activeKey || '', term = '', data;
  try { data = JSON.parse(document.getElementById('msgr-inbox-initial').textContent); } catch (e) { data = { items: [], total_unread: 0 }; }

  function chatUrl(id) { return root.dataset.chatUrl.replace('/0/', '/' + id + '/'); }

  function preview(it) {
    if (!it.last) return 'هنوز پیامی نیست';
    var who = it.last.mine ? 'شما: ' : (it.is_main ? it.last.sender + ': ' : '');
    return who + it.last.text;
  }

  function openDirect(it) {
    M.api(root.dataset.openUrl.replace('/0/', '/' + it.peer_id + '/'), {}).then(function (r) {
      if (r.ok) window.location.href = chatUrl(r.conv_id);
    });
  }

  function row(it) {
    var li = M.el('li');
    var a = M.el('a', 'flex items-center gap-3 px-4 py-3 border-b border-base-200 hover:bg-base-200' +
                 (it.key === activeKey ? ' bg-base-200' : ''));
    a.href = it.conv_id ? chatUrl(it.conv_id) : '#';
    a.appendChild(M.avatar(it.title, it.is_main, 'w-12'));
    var body = M.el('div', 'flex-1 min-w-0 flex flex-col gap-0.5');
    var top = M.el('div', 'flex items-center justify-between gap-2');
    top.appendChild(M.el('span', 'font-semibold text-sm truncate', it.title));
    if (it.last) top.appendChild(M.el('span', 'text-xs fb-muted shrink-0', M.listTime(it.last.at)));
    var bottom = M.el('div', 'flex items-center justify-between gap-2');
    bottom.appendChild(M.el('span', 'text-xs fb-muted truncate', preview(it)));
    var tail = M.el('span', 'flex items-center gap-1 shrink-0');
    if (it.muted) tail.appendChild(M.icon('bell-off', 'w-3.5 h-3.5 opacity-50'));
    if (it.unread) tail.appendChild(M.el('span', 'fb-badge ' + (it.muted ? 'fb-badge-neutral' : 'fb-badge-primary'), M.fa(it.unread)));
    bottom.appendChild(tail);
    body.appendChild(top); body.appendChild(bottom);
    a.appendChild(body);
    if (!it.conv_id) a.addEventListener('click', function (e) { e.preventDefault(); openDirect(it); });
    li.appendChild(a);
    return li;
  }

  function render(d) {
    data = d;
    M.setBadge(d.total_unread || 0);
    list.textContent = '';
    var shown = d.items.filter(function (it) { return !term || M.norm(it.title).indexOf(term) !== -1; });
    if (!shown.length) { list.appendChild(M.el('li', 'p-6 text-center text-sm fb-muted', 'موردی پیدا نشد.')); return; }
    shown.forEach(function (it) { list.appendChild(row(it)); });
  }

  if (search) search.addEventListener('input', function () { term = M.norm(search.value); render(data); });
  render(data);
  M.poll(function () {
    return M.api(root.dataset.inboxUrl).then(function (r) { if (r.ok) render(r); });
  }, 10000);
})();
