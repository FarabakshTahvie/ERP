(function () {
  // opts: {url, name, multi, placeholder, ariaLabel, onSelect}
  window.fbRemotePicker = function (opts) {
    var container = document.createElement('div');
    container.className = 'flex flex-col gap-2';

    var wrap = document.createElement('div');
    wrap.className = 'relative';

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'input input-sm w-full';
    input.placeholder = opts.placeholder || 'جستجو (حداقل ۲ حرف)...';
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
    container.appendChild(wrap);

    var chipsWrap = null;
    var selectedIds = new Set();

    if (opts.multi) {
      chipsWrap = document.createElement('div');
      chipsWrap.className = 'flex flex-wrap gap-1.5 mt-2';
      container.appendChild(chipsWrap);
    }

    var timer = null;
    var currentResults = [];
    var activeIndex = -1;

    function open() { list.classList.remove('hidden'); input.setAttribute('aria-expanded', 'true'); }
    function close() { list.classList.add('hidden'); input.setAttribute('aria-expanded', 'false'); activeIndex = -1; }

    function paint() {
      var buttons = list.querySelectorAll('button');
      Array.prototype.forEach.call(buttons, function (b, i) {
        b.classList.toggle('menu-active', i === activeIndex);
      });
    }

    function scrollActive() {
      var buttons = list.querySelectorAll('button');
      var b = buttons[activeIndex];
      if (b && b.scrollIntoView) b.scrollIntoView({ block: 'nearest' });
    }

    function addChip(item) {
      if (selectedIds.has(String(item.id))) return;
      selectedIds.add(String(item.id));

      var chip = document.createElement('span');
      chip.className = 'fb-badge fb-badge-neutral gap-1';
      chip.textContent = item.name;

      var hiddenInput = document.createElement('input');
      hiddenInput.type = 'hidden';
      hiddenInput.name = opts.name || 'audience_users';
      hiddenInput.value = item.id;
      chip.appendChild(hiddenInput);

      var btnRemove = document.createElement('button');
      btnRemove.type = 'button';
      btnRemove.className = 'btn btn-ghost btn-xs btn-circle text-base-content/60 hover:text-error';
      btnRemove.textContent = '×';
      btnRemove.addEventListener('click', function () {
        selectedIds.delete(String(item.id));
        chip.remove();
      });
      chip.appendChild(btnRemove);

      if (chipsWrap) chipsWrap.appendChild(chip);
    }

    function choose(item) {
      if (opts.multi) {
        addChip(item);
        input.value = '';
        close();
      } else {
        input.value = item.name;
        close();
        if (opts.onSelect) opts.onSelect(item);
      }
    }

    function renderResults(results) {
      currentResults = results || [];
      list.textContent = '';
      if (!currentResults.length) {
        var li = document.createElement('li');
        var sp = document.createElement('span');
        sp.className = 'fb-hint px-3 py-2 block';
        sp.textContent = 'موردی پیدا نشد';
        li.appendChild(sp);
        list.appendChild(li);
        open();
        return;
      }

      currentResults.forEach(function (item, idx) {
        var li = document.createElement('li');
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'flex flex-col items-start w-full px-3 py-1.5 text-right';
        b.setAttribute('role', 'option');

        var nameSpan = document.createElement('span');
        nameSpan.className = 'font-medium text-sm';
        nameSpan.textContent = item.name;
        b.appendChild(nameSpan);

        if (item.sub) {
          var subSpan = document.createElement('span');
          subSpan.className = 'text-xs fb-muted';
          subSpan.textContent = item.sub;
          b.appendChild(subSpan);
        }

        b.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          choose(item);
        });

        li.appendChild(b);
        list.appendChild(li);
      });

      activeIndex = 0;
      paint();
      open();
    }

    function fetchQuery(q) {
      if (q.length < 2) {
        close();
        return;
      }
      var url = opts.url + (opts.url.indexOf('?') === -1 ? '?' : '&') + 'q=' + encodeURIComponent(q);
      fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          renderResults(data.results || []);
        })
        .catch(function () {
          list.textContent = '';
          var li = document.createElement('li');
          var sp = document.createElement('span');
          sp.className = 'text-error px-3 py-2 block text-xs';
          sp.textContent = 'خطا در جستجو';
          li.appendChild(sp);
          list.appendChild(li);
          open();
        });
    }

    input.addEventListener('input', function () {
      var q = input.value.trim();
      clearTimeout(timer);
      if (q.length < 2) {
        close();
        return;
      }
      timer = setTimeout(function () {
        fetchQuery(q);
      }, 300);
    });

    input.addEventListener('blur', function () {
      setTimeout(close, 200);
    });

    input.addEventListener('keydown', function (ev) {
      var isOpen = !list.classList.contains('hidden');
      if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        if (!isOpen && currentResults.length) { open(); }
        activeIndex = Math.min(currentResults.length - 1, activeIndex + 1);
        paint();
        scrollActive();
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
        activeIndex = Math.max(0, activeIndex - 1);
        paint();
        scrollActive();
      } else if (ev.key === 'Enter') {
        ev.preventDefault();
        if (isOpen && activeIndex >= 0 && currentResults[activeIndex]) {
          choose(currentResults[activeIndex]);
        }
      } else if (ev.key === 'Escape') {
        close();
      }
    });

    (opts.initial || []).forEach(addChip);
    return container;
  };
})();
