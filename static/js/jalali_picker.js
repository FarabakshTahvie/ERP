(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹', DAY = 86400000;
  var MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  var WEEK = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
  var fmt = new Intl.DateTimeFormat('fa-IR-u-nu-latn', { year: 'numeric', month: 'numeric', day: 'numeric', timeZone: 'UTC' });
  var pop = null, current = null, view = { y: 0, m: 0 };

  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function en(s) { return String(s || '').replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); }).replace(/[٠-٩]/g, function (d) { return '٠١٢٣٤٥٦٧٨٩'.indexOf(d); }); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function pad(n) { return n < 10 ? '0' + n : String(n); }

  function toJ(ms) {
    var o = {};
    fmt.formatToParts(new Date(ms)).forEach(function (p) { o[p.type] = parseInt(p.value, 10); });
    return { y: o.year, m: o.month, d: o.day };
  }
  function cmp(a, y, m, d) { return a.y !== y ? a.y - y : a.m !== m ? a.m - m : a.d - d; }
  function firstOfMonth(y, m) {
    var off = m <= 7 ? 31 * (m - 1) : 186 + 30 * (m - 7);
    var ms = Date.UTC(y + 621, 2, 21, 12) + off * DAY;
    for (var i = 0; i < 12; i++) {
      var c = cmp(toJ(ms), y, m, 1);
      if (c === 0) return ms;
      ms += c > 0 ? -DAY : DAY;
    }
    return ms;
  }
  function monthInfo(y, m) {
    var start = firstOfMonth(y, m), n = 0;
    while (n < 31 && toJ(start + n * DAY).m === m) n++;
    return { start: start, days: n, lead: (new Date(start).getUTCDay() + 1) % 7 };   // شنبه = ۰
  }
  function todayJ() { var n = new Date(); return toJ(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate(), 12)); }
  function parse(v) {
    var m = en(v).match(/(\d{4})\D+(\d{1,2})\D+(\d{1,2})/);
    return m ? { y: +m[1], m: +m[2], d: +m[3] } : null;
  }

  function pick(y, m, d) {
    current.value = fa(y) + '/' + fa(pad(m)) + '/' + fa(pad(d));
    current.dispatchEvent(new Event('input', { bubbles: true }));
    current.dispatchEvent(new Event('change', { bubbles: true }));
    close();
  }
  function close() { if (pop) pop.classList.add('hidden'); current = null; }

  function render() {
    var info = monthInfo(view.y, view.m), sel = parse(current.value), today = todayJ();
    pop.textContent = '';
    var head = el('div', 'flex items-center gap-1 mb-2');
    var prev = el('button', 'btn btn-ghost btn-xs', 'قبل ›'); prev.type = 'button';
    var next = el('button', 'btn btn-ghost btn-xs', '‹ بعد'); next.type = 'button';
    var ms = el('select', 'select select-xs flex-1 min-w-0'), ys = el('select', 'select select-xs w-20');
    MONTHS.forEach(function (n, i) { var o = el('option', null, n); o.value = i + 1; if (i + 1 === view.m) o.selected = true; ms.appendChild(o); });
    for (var y = view.y - 10; y <= view.y + 10; y++) { var o = el('option', null, fa(y)); o.value = y; if (y === view.y) o.selected = true; ys.appendChild(o); }
    function go(dm) { view.m += dm; if (view.m > 12) { view.m = 1; view.y++; } if (view.m < 1) { view.m = 12; view.y--; } render(); }
    prev.addEventListener('click', function () { go(-1); });
    next.addEventListener('click', function () { go(1); });
    ms.addEventListener('change', function () { view.m = +ms.value; render(); });
    ys.addEventListener('change', function () { view.y = +ys.value; render(); });
    [prev, ms, ys, next].forEach(function (n) { head.appendChild(n); });
    pop.appendChild(head);

    var grid = el('div', 'grid grid-cols-7 gap-1 text-center');
    WEEK.forEach(function (w) { grid.appendChild(el('span', 'text-xs fb-muted py-1', w)); });
    for (var i = 0; i < info.lead; i++) grid.appendChild(el('span'));
    for (var d = 1; d <= info.days; d++) {
      var isSel = sel && sel.y === view.y && sel.m === view.m && sel.d === d;
      var isToday = today.y === view.y && today.m === view.m && today.d === d;
      var b = el('button', 'btn btn-xs font-technical ' + (isSel ? 'btn-primary' : 'btn-ghost') + (isToday && !isSel ? ' border border-primary' : ''), fa(d));
      b.type = 'button';
      (function (day) { b.addEventListener('click', function () { pick(view.y, view.m, day); }); })(d);
      grid.appendChild(b);
    }
    pop.appendChild(grid);

    var foot = el('div', 'flex justify-between mt-2');
    var t = el('button', 'btn btn-ghost btn-xs', 'امروز'); t.type = 'button';
    t.addEventListener('click', function () { pick(today.y, today.m, today.d); });
    foot.appendChild(t);
    if (current.hasAttribute('data-clearable')) {
      var c = el('button', 'btn btn-ghost btn-xs', 'پاک‌کردن'); c.type = 'button';
      c.addEventListener('click', function () { current.value = ''; current.dispatchEvent(new Event('change', { bubbles: true })); close(); });
      foot.appendChild(c);
    }
    pop.appendChild(foot);
  }

  function open(input) {
    if (input.disabled || current === input) return;
    if (!pop) {
      pop = el('div', 'absolute z-50 bg-base-100 border border-base-300 rounded-box shadow-lg p-3 w-72 hidden');
      pop.dir = 'rtl';
      pop.addEventListener('mousedown', function (e) { e.preventDefault(); });
      pop.addEventListener('click', function (e) { e.stopPropagation(); });   // رندر دوباره دکمه را از DOM برمی‌دارد؛ بیرون‌کلیک حساب نشود
      document.body.appendChild(pop);
    }
    current = input;
    var s = parse(input.value) || todayJ();
    view = { y: s.y, m: s.m };
    render();
    var r = input.getBoundingClientRect(), w = document.documentElement.clientWidth;
    var left = Math.min(Math.max(8, r.right - 288), w - 296);
    pop.style.left = (left + window.scrollX) + 'px';
    pop.style.top = (r.bottom + window.scrollY + 4) + 'px';
    pop.classList.remove('hidden');
  }

  document.addEventListener('focusin', function (e) { if (e.target.matches && e.target.matches('[data-jalali-date]')) open(e.target); });
  document.addEventListener('click', function (e) {
    if (e.target.matches && e.target.matches('[data-jalali-date]')) open(e.target); else close();
  });
  document.addEventListener('keydown', function (e) {
    if (!e.target.matches || !e.target.matches('[data-jalali-date]')) return;
    if (e.key === 'Tab' || e.key === 'Escape') { close(); return; }
    if (e.key.length === 1 || e.key === 'Backspace' || e.key === 'Delete') e.preventDefault();   // تایپ دستی ممنوع
  });
  document.addEventListener('paste', function (e) { if (e.target.matches && e.target.matches('[data-jalali-date]')) e.preventDefault(); });
})();
