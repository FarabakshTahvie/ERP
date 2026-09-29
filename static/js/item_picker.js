(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹', AR = '٠١٢٣٤٥٦٧٨٩';

  function norm(s) {
    return String(s == null ? '' : s).toLowerCase()
      .replace(/ي/g, 'ی').replace(/ك/g, 'ک')
      .replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return AR.indexOf(d); })
      .replace(/[\u200c\u200e\u200f]/g, ' ')
      .replace(/\s+/g, ' ').trim();
  }
  window.fbNormalizeFa = norm;

  // opts: {items:[{id,name,unit?}], placeholder?, ariaLabel?, onSelect(rawItem|null)}
  window.fbItemPicker = function (opts) {
    var items = [], selected = null, active = -1, shown = [];

    function make(it) { return { raw: it, name: String(it.name), n: norm(it.name) }; }
    (opts.items || []).forEach(function (it) { items.push(make(it)); });

    var wrap = document.createElement('div');
    wrap.className = 'relative';
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'input input-sm w-full';
    input.placeholder = opts.placeholder || 'جستجوی کالا...';
    input.autocomplete = 'off';
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    if (opts.ariaLabel) input.setAttribute('aria-label', opts.ariaLabel);
    var list = document.createElement('ul');
    list.className = 'menu absolute z-40 mt-1 w-full max-h-60 overflow-y-auto flex-nowrap bg-base-100 border border-base-300 rounded-box shadow-lg hidden';
    list.setAttribute('role', 'listbox');
    wrap.appendChild(input);
    wrap.appendChild(list);

    function open() { list.classList.remove('hidden'); input.setAttribute('aria-expanded', 'true'); }
    function close() { list.classList.add('hidden'); input.setAttribute('aria-expanded', 'false'); active = -1; }
    function paint() {
      Array.prototype.forEach.call(list.querySelectorAll('button'), function (b, i) {
        b.classList.toggle('menu-active', i === active);
      });
    }
    function scrollActive() {
      var b = list.querySelectorAll('button')[active];
      if (b && b.scrollIntoView) b.scrollIntoView({ block: 'nearest' });
    }
    function choose(entry) {
      selected = entry;
      input.value = entry.name;
      close();
      if (opts.onSelect) opts.onSelect(entry.raw);
    }
    function render() {
      var tokens = norm(input.value).split(' ').filter(Boolean);
      shown = items.filter(function (e) {
        return tokens.every(function (t) { return e.n.indexOf(t) !== -1; });
      }).slice(0, 50);
      list.textContent = '';
      if (!shown.length) {
        var li = document.createElement('li'), sp = document.createElement('span');
        sp.className = 'fb-hint px-3 py-2 block';
        sp.textContent = 'موردی پیدا نشد';
        li.appendChild(sp);
        list.appendChild(li);
        return;
      }
      shown.forEach(function (e) {
        var li = document.createElement('li'), b = document.createElement('button');
        b.type = 'button';
        b.setAttribute('role', 'option');
        b.textContent = e.name;
        if (e.raw.unit) {
          var u = document.createElement('span');
          u.className = 'text-xs fb-muted';
          u.textContent = e.raw.unit;
          b.appendChild(u);
        }
        b.addEventListener('mousedown', function (ev) { ev.preventDefault(); choose(e); });
        li.appendChild(b);
        list.appendChild(li);
      });
      active = tokens.length ? 0 : -1;
      paint();
    }

    list.addEventListener('mousedown', function (ev) { ev.preventDefault(); });   // اسکرول لیست فوکوس را نپراند
    input.addEventListener('input', function () {
      if (selected) { selected = null; if (opts.onSelect) opts.onSelect(null); }
      render(); open();
    });
    input.addEventListener('focus', function () { input.select(); render(); open(); });
    input.addEventListener('blur', close);
    input.addEventListener('keydown', function (ev) {
      var isOpen = !list.classList.contains('hidden');
      if (ev.key === 'ArrowDown') {
        ev.preventDefault(); if (!isOpen) { render(); open(); }
        active = Math.min(shown.length - 1, active + 1); paint(); scrollActive();
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault(); active = Math.max(0, active - 1); paint(); scrollActive();
      } else if (ev.key === 'Enter' && isOpen) {
        ev.preventDefault();
        if (active >= 0 && shown[active]) choose(shown[active]);
      } else if (ev.key === 'Escape') {
        close();
      }
    });

    return {
      el: wrap,
      getId: function () { return selected ? selected.raw.id : null; },
      select: function (id) {
        for (var i = 0; i < items.length; i++) {
          if (items[i].raw.id === id) { choose(items[i]); return; }
        }
      },
      addItem: function (it) { items.push(make(it)); },
      focus: function () { input.focus(); }
    };
  };
})();
