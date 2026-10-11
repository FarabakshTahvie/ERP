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

  // capture: قبل از شنونده‌های خودِ کادر (مثل fbLineEditor) اجرا شود تا آن‌ها مقدار تمیز را بخوانند
  document.addEventListener('input', function (e) {
    var el = e.target;
    if (e.isComposing || !el || !el.matches) return;
    var fn = el.matches('input[data-money]') ? digitsOnly : el.matches('input[data-decimal]') ? decimalOnly : null;
    if (!fn) return;
    var before = el.value, next = fn(before);
    if (next === before) return;
    var pos = el.selectionStart;
    var caret = pos == null ? next.length : fn(before.slice(0, pos)).length;
    el.value = next;
    try { el.setSelectionRange(caret, caret); } catch (err) {}
  }, true);
})();
