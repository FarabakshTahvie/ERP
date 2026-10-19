(function () {
  var FA = '۰۱۲۳۴۵۶۷۸۹', AR = '٠١٢٣٤٥٦٧٨٩';

  function latin(s) {
    return String(s == null ? '' : s)
      .replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return AR.indexOf(d); });
  }
  function digitsOnly(s) {
    return latin(s).replace(/\D/g, '');
  }
  function decimalOnly(s) {
    var t = latin(s).replace(/٫/g, '.').replace(/[^0-9.]/g, '');
    var i = t.indexOf('.');
    return i === -1 ? t : t.slice(0, i + 1) + t.slice(i + 1).replace(/\./g, '');
  }
  function group(digits) {
    return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  // maxlength روی کادر مبلغ یعنی «حداکثر رقم»؛ کاماها از آن حساب نمی‌شوند، پس خودِ مرورگر نباید طول را ببرد
  function prepare(el) {
    if (el.dataset.maxDigits !== undefined) return;
    var max = parseInt(el.getAttribute('maxlength'), 10);
    el.dataset.maxDigits = max > 0 ? String(max) : '';
    if (max > 0) el.removeAttribute('maxlength');
  }

  function formatMoney(el) {
    prepare(el);
    var before = el.value, pos = el.selectionStart;
    var digits = digitsOnly(before);
    var max = parseInt(el.dataset.maxDigits, 10);
    if (max > 0 && digits.length > max) digits = digits.slice(0, max);
    var next = group(digits);
    if (next === before) return;
    var left = pos == null ? digits.length : Math.min(digitsOnly(before.slice(0, pos)).length, digits.length);
    el.value = next;
    if (document.activeElement !== el) return;
    var idx = 0, seen = 0;
    while (idx < next.length && seen < left) {
      if (next.charAt(idx) !== ',') seen++;
      idx++;
    }
    try { el.setSelectionRange(idx, idx); } catch (err) {}
  }
  window.fbMoney = { format: formatMoney, digits: digitsOnly };

  // capture: قبل از شنونده‌های خودِ کادر (مثل fbLineEditor) اجرا شود تا آن‌ها مقدار تمیز را بخوانند
  document.addEventListener('input', function (e) {
    var el = e.target;
    if (e.isComposing || !el || !el.matches) return;
    if (el.matches('input[data-money]')) { formatMoney(el); return; }
    var fn = el.matches('input[data-digits]') ? digitsOnly : el.matches('input[data-decimal]') ? decimalOnly : null;
    if (!fn) return;
    var before = el.value, next = fn(before);
    if (next === before) return;
    var pos = el.selectionStart;
    var caret = pos == null ? next.length : fn(before.slice(0, pos)).length;
    el.value = next;
    try { el.setSelectionRange(caret, caret); } catch (err) {}
  }, true);

  document.addEventListener('focusin', function (e) {
    var el = e.target;
    if (el && el.matches && el.matches('input[data-money]')) formatMoney(el);
  });

  function init() {
    document.querySelectorAll('input[data-money]').forEach(formatMoney);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
