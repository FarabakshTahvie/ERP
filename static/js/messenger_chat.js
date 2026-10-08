(function () {
  var M = window.fbMsgr, root = document.querySelector('[data-msgr-chat]');
  if (!M || !root) return;
  var MINE = 'chat-start', OTHER = 'chat-end';   // صفحه RTL است: start = راست. اگر پیام‌های خودم چپ دیده شد، این دو را جابه‌جا کن.
  var ds = root.dataset, me = +ds.me, isMain = ds.isMain === '1', canModerate = ds.canModerate === '1';
  var scroll = root.querySelector('[data-msgr-scroll]'), feed = root.querySelector('[data-msgr-feed]');
  var olderBtn = root.querySelector('[data-msgr-older]'), jump = root.querySelector('[data-msgr-jump]');
  var jumpCount = root.querySelector('[data-jump-count]');
  var form = root.querySelector('[data-msgr-form]'), ta = form.querySelector('textarea');
  var sendBtn = form.querySelector('button[type=submit]');
  var bar = root.querySelector('[data-msgr-bar]'), barTitle = bar.querySelector('[data-bar-title]');
  var barText = bar.querySelector('[data-bar-text]');
  var errBox = root.querySelector('[data-msgr-error]'), muteBtn = root.querySelector('[data-msgr-mute]');
  var init = JSON.parse(document.getElementById('msgr-chat-initial').textContent);

  var firstId = 0, lastId = 0, hasMore = !!init.has_more, since = init.now, peerRead = init.peer_read_id;
  var loadingOlder = false, replyTo = null, editing = null, sentRead = 0, unseen = 0, muted = ds.muted === '1';
  var pendings = {}, errTimer = null;
  var coarse = window.matchMedia && matchMedia('(pointer: coarse)').matches;

  function url(key, id) { return ds[key].replace('/0/', '/' + id + '/'); }
  function nearBottom() { return scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 120; }
  function toBottom() { scroll.scrollTop = scroll.scrollHeight; }
  function flash(msg) {
    errBox.textContent = msg || 'ثبت نشد.';
    errBox.classList.remove('hidden');
    clearTimeout(errTimer);
    errTimer = setTimeout(function () { errBox.classList.add('hidden'); }, 6000);
  }
  function small(icon, label, fn, cls) {
    var b = M.el('button', 'btn btn-ghost btn-xs gap-1 ' + (cls || ''));
    b.type = 'button';
    b.appendChild(M.icon(icon, 'w-3.5 h-3.5'));
    b.appendChild(M.el('span', null, label));
    b.addEventListener('click', function (e) { e.stopPropagation(); fn(b); });
    return b;
  }

  // ---------- ساخت حباب ----------
  function quote(r) {
    var q = M.el('div', 'border-s-2 border-current/50 ps-2 mb-1 text-xs opacity-80 cursor-pointer');
    q.dataset.replyTo = r.id;
    q.appendChild(M.el('div', 'font-semibold', r.name));
    q.appendChild(M.el('div', 'truncate', r.snippet));
    return q;
  }

  function build(m) {
    var wrap = M.el('div', 'chat ' + (m.mine ? MINE : OTHER));
    wrap._m = m;
    wrap.dataset.msg = '1';
    wrap.dataset.ts = m.ts;
    if (m.id) wrap.dataset.id = m.id;
    if (m.uid) wrap.dataset.uid = m.uid;
    if (m.pending || m.failed) wrap.dataset.pending = '1';
    if (!m.mine && isMain) wrap.appendChild(M.el('div', 'chat-header text-xs fb-muted', m.sender.name));

    var bubble = M.el('div', 'chat-bubble max-w-[85%] sm:max-w-[70%] cursor-pointer' + (m.mine ? ' chat-bubble-primary' : ''));
    if (m.deleted) {
      bubble.classList.add('italic', 'opacity-60');
      bubble.textContent = 'این پیام حذف شد';
    } else {
      if (m.reply) bubble.appendChild(quote(m.reply));
      var p = M.el('div', 'whitespace-pre-wrap [overflow-wrap:anywhere]');
      p.dir = 'auto';
      M.fill(p, m.text);
      bubble.appendChild(p);
    }
    wrap.appendChild(bubble);

    var foot = M.el('div', 'chat-footer flex items-center gap-2 text-[10px]');
    if (m.failed) {
      foot.appendChild(M.el('span', 'text-error', m.error || 'ارسال نشد'));
      foot.appendChild(small('refresh-cw', 'تلاش مجدد', function () { retry(m.uid); }));
      foot.appendChild(small('x', 'حذف', function () { discard(m.uid); }));
    } else if (m.pending) {
      foot.appendChild(M.icon('clock', 'w-3 h-3'));
      foot.appendChild(M.el('span', null, 'در حال ارسال'));
    } else {
      foot.appendChild(M.el('span', 'opacity-60', M.clock(m.at)));
      if (m.edited && !m.deleted) foot.appendChild(M.el('span', 'opacity-60', 'ویرایش‌شده'));
      if (m.mine) { var t = M.el('span'); t.dataset.tick = '1'; foot.appendChild(t); }
    }
    wrap.appendChild(foot);
    return wrap;
  }

  function updateTicks() {
    feed.querySelectorAll('[data-tick]').forEach(function (t) {
      var id = +t.closest('[data-msg]').dataset.id;
      var seen = peerRead != null && id <= peerRead;
      t.textContent = '';
      t.appendChild(M.icon(seen ? 'check-check' : 'check', 'w-3.5 h-3.5' + (seen ? ' text-info' : ' opacity-60')));
    });
  }

  function refreshSeparators() {
    feed.querySelectorAll('[data-sep]').forEach(function (n) { n.remove(); });
    var prev = null;
    Array.prototype.forEach.call(feed.querySelectorAll('[data-msg]'), function (n) {
      var day = new Date(+n.dataset.ts * 1000).toDateString();
      if (day !== prev) {
        var sep = M.el('div', 'flex justify-center my-2');
        sep.dataset.sep = '1';
        sep.appendChild(M.el('span', 'fb-badge fb-badge-neutral', M.dayLabel(+n.dataset.ts)));
        feed.insertBefore(sep, n);
        prev = day;
      }
    });
  }

  // درج پیام واقعی؛ خروجی true یعنی گره تازه اضافه شد
  function upsert(m) {
    var node = feed.querySelector('[data-id="' + m.id + '"]');
    var fresh = build(m);
    if (m.id > lastId) lastId = m.id;
    if (!firstId || m.id < firstId) firstId = m.id;
    if (node) { node.replaceWith(fresh); return false; }
    var pend = m.uid ? feed.querySelector('[data-uid="' + m.uid + '"][data-pending]') : null;
    if (pend) { pend.replaceWith(fresh); return false; }
    var firstPending = feed.querySelector('[data-pending]');
    if (firstPending) feed.insertBefore(fresh, firstPending); else feed.appendChild(fresh);
    return true;
  }

  // ---------- عملیات روی پیام ----------
  function closeActions() { feed.querySelectorAll('[data-actions]').forEach(function (n) { n.remove(); }); }

  function toggleActions(wrap) {
    var had = wrap.querySelector('[data-actions]');
    closeActions();
    var m = wrap._m;
    if (had || !m || !m.id || m.deleted) return;
    var row = M.el('div', 'flex flex-wrap gap-1 mt-1');
    row.dataset.actions = '1';
    row.appendChild(small('reply', 'پاسخ', function () { startReply(m); }));
    row.appendChild(small('copy', 'کپی', function (b) {
      if (navigator.clipboard) navigator.clipboard.writeText(m.text).then(function () {
        b.lastChild.textContent = 'کپی شد';
        setTimeout(function () { b.lastChild.textContent = 'کپی'; }, 1200);
      });
    }));
    if (m.mine && Date.now() / 1000 - m.ts < 48 * 3600) row.appendChild(small('pencil', 'ویرایش', function () { startEdit(m); }));
    if (m.mine || (isMain && canModerate)) row.appendChild(small('trash-2', 'حذف', function () { removeMsg(m); }, 'text-error'));
    wrap.appendChild(row);
  }

  function setBar(title, text) {
    barTitle.textContent = title;
    barText.textContent = text;
    bar.classList.remove('hidden');
  }
  function cancelBar() {
    if (editing) { ta.value = ''; autosize(); }
    replyTo = null; editing = null;
    bar.classList.add('hidden');
  }
  function startReply(m) {
    cancelBar(); closeActions();
    replyTo = { id: m.id, name: m.sender.name, snippet: m.text.slice(0, 80) };
    setBar('پاسخ به ' + m.sender.name, m.text.slice(0, 80));
    ta.focus();
  }
  function startEdit(m) {
    cancelBar(); closeActions();
    editing = m;
    ta.value = m.text; autosize();
    setBar('ویرایش پیام', m.text.slice(0, 80));
    ta.focus();
  }
  function removeMsg(m) {
    closeActions();
    if (!window.confirm('این پیام حذف شود؟')) return;
    M.api(url('deleteUrl', m.id), {}).then(function (r) {
      if (r.ok) { upsert(r.message); updateTicks(); } else flash(r.error);
    });
  }

  function jumpTo(id) {
    var n = feed.querySelector('[data-id="' + id + '"]');
    if (!n) return;
    n.scrollIntoView({ block: 'center', behavior: 'smooth' });
    n.classList.add('ring-2', 'ring-primary', 'rounded-box');
    setTimeout(function () { n.classList.remove('ring-2', 'ring-primary', 'rounded-box'); }, 1400);
  }

  feed.addEventListener('click', function (e) {
    var q = e.target.closest('[data-reply-to]');
    if (q) { e.stopPropagation(); jumpTo(+q.dataset.replyTo); return; }
    if (e.target.closest('a, button, [data-actions]')) return;
    var w = e.target.closest('[data-msg]');
    if (w) toggleActions(w);
  });

  // ---------- ارسال ----------
  function paint(p, extra) {
    var fresh = build(Object.assign({}, p.m, extra || {}));
    var old = feed.querySelector('[data-uid="' + p.uid + '"]');
    if (old) old.replaceWith(fresh); else feed.appendChild(fresh);
  }
  function submit(p) {
    paint(p, { pending: true });
    M.api(ds.sendUrl, { text: p.text, client_uid: p.uid, reply_to: p.reply ? p.reply.id : '' }).then(function (r) {
      if (r.ok) {
        delete pendings[p.uid];
        upsert(r.message); refreshSeparators(); updateTicks(); toBottom(); markRead();
      } else {
        paint(p, { failed: true, error: r.error });
      }
    });
  }
  function retry(uid) { if (pendings[uid]) submit(pendings[uid]); }
  function discard(uid) {
    delete pendings[uid];
    var n = feed.querySelector('[data-uid="' + uid + '"]');
    if (n) n.remove();
    refreshSeparators();
  }

  function doEdit(text) {
    var m = editing;
    if (text === m.text) { cancelBar(); return; }
    sendBtn.disabled = true;
    M.api(url('editUrl', m.id), { text: text }).then(function (r) {
      sendBtn.disabled = false;
      if (r.ok) { cancelBar(); upsert(r.message); updateTicks(); } else flash(r.error);
    });
  }

  function send() {
    var text = ta.value.trim();
    if (!text) return;
    if (editing) { doEdit(text); return; }
    var uid = M.uuid(), reply = replyTo;
    var p = { uid: uid, text: text, reply: reply };
    p.m = { mine: true, text: text, uid: uid, reply: reply, ts: Date.now() / 1000, at: new Date().toISOString(),
            sender: { id: me, name: '' } };
    pendings[uid] = p;
    cancelBar();
    ta.value = ''; autosize();
    paint(p, { pending: true });
    refreshSeparators(); toBottom();
    submit(p);
  }

  // ---------- textarea ----------
  function autosize() {
    var near = nearBottom();
    ta.style.height = 'auto';
    var cs = getComputedStyle(ta);
    var line = parseFloat(cs.lineHeight) || 24;
    var extra = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) +
                parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
    var max = line * 3 + extra;
    ta.style.height = Math.min(ta.scrollHeight + (cs.boxSizing === 'border-box' ? parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) : 0), max) + 'px';
    ta.style.overflowY = ta.scrollHeight > max ? 'auto' : 'hidden';
    if (near) toBottom();
  }
  ta.addEventListener('input', autosize);
  ta.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !coarse && !e.isComposing) { e.preventDefault(); send(); }
    if (e.key === 'Escape') cancelBar();
  });
  form.addEventListener('submit', function (e) { e.preventDefault(); send(); });
  bar.querySelector('[data-bar-cancel]').addEventListener('click', cancelBar);

  // ---------- خوانده‌شدن، پیام‌های قدیمی، پولینگ ----------
  function markRead() {
    if (document.hidden || lastId <= sentRead || !nearBottom()) return;
    sentRead = lastId;
    M.api(ds.readUrl, { up_to: lastId });
  }
  function setJump() {
    jumpCount.textContent = M.fa(unseen);
    jumpCount.classList.toggle('hidden', !unseen);
  }

  function loadOlder() {
    if (!hasMore || loadingOlder || !firstId) return;
    loadingOlder = true;
    var h = scroll.scrollHeight, t = scroll.scrollTop;
    M.api(ds.messagesUrl + '?before=' + firstId).then(function (r) {
      loadingOlder = false;
      if (!r.ok) return;
      hasMore = r.has_more;
      olderBtn.classList.toggle('hidden', !hasMore);
      var frag = document.createDocumentFragment();
      r.messages.forEach(function (m) { frag.appendChild(build(m)); });
      if (r.messages.length) firstId = r.messages[0].id;
      feed.insertBefore(frag, feed.firstChild);
      refreshSeparators(); updateTicks();
      scroll.scrollTop = t + (scroll.scrollHeight - h);
    });
  }
  olderBtn.querySelector('button').addEventListener('click', loadOlder);

  scroll.addEventListener('scroll', function () {
    if (scroll.scrollTop < 80) loadOlder();
    var near = nearBottom();
    jump.classList.toggle('hidden', near);
    if (near) { unseen = 0; setJump(); markRead(); }
  }, { passive: true });
  jump.addEventListener('click', function () { toBottom(); });

  function pollOnce() {
    return M.api(ds.messagesUrl + '?after=' + lastId + '&since=' + since).then(function (r) {
      if (!r.ok) return;
      since = r.now;
      peerRead = r.peer_read_id;
      var near = nearBottom(), added = 0;
      r.messages.forEach(function (m) { if (upsert(m)) added++; });
      r.updates.forEach(function (m) {
        var n = feed.querySelector('[data-id="' + m.id + '"]');
        if (n) n.replaceWith(build(m));
      });
      refreshSeparators(); updateTicks();
      if (added && near) { toBottom(); markRead(); }
      else if (added) { unseen += added; setJump(); jump.classList.remove('hidden'); }
    });
  }

  // ---------- بی‌صدا ----------
  function paintMute() {
    muteBtn.textContent = '';
    muteBtn.appendChild(M.icon(muted ? 'bell-off' : 'bell', 'w-4 h-4'));
    var label = muted ? 'فعال‌کردن اعلان این گفت‌وگو' : 'بی‌صداکردن این گفت‌وگو';
    muteBtn.setAttribute('aria-label', label);
    muteBtn.title = label;
  }
  muteBtn.addEventListener('click', function () {
    var next = !muted;
    muteBtn.disabled = true;
    M.api(ds.muteUrl, { muted: next ? '1' : '0' }).then(function (r) {
      muteBtn.disabled = false;
      if (r.ok) { muted = next; paintMute(); } else flash(r.error);
    });
  });

  // ---------- شروع ----------
  init.messages.forEach(upsert);
  refreshSeparators(); updateTicks(); paintMute();
  olderBtn.classList.toggle('hidden', !hasMore);
  toBottom(); markRead();
  if (!coarse) ta.focus();
  M.poll(pollOnce, 10000);
})();
