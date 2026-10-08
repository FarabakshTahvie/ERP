(function () {
  var box = document.querySelector('[data-notify-guide]');
  var dlg = document.querySelector('[data-notify-dialog]');
  if (!box || !dlg) return;
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function q(sel, root) { return (root || document).querySelector(sel); }
  var badge = q('[data-notify-badge]', box), text = q('[data-notify-text]', box);
  var enable = q('[data-notify-enable]', box), openBtn = q('[data-notify-open]', box);
  var devices = parseInt(box.dataset.devices, 10) || 0;

  var ua = navigator.userAgent || '';
  var os = (/iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)) ? 'ios'
    : /Android/.test(ua) ? 'android' : /Windows/.test(ua) ? 'windows' : /Mac/.test(ua) ? 'mac'
    : /Linux|X11|CrOS/.test(ua) ? 'linux' : 'other';
  var browser = /SamsungBrowser/.test(ua) ? 'samsung' : /Edg\/|EdgA\/|EdgiOS/.test(ua) ? 'edge'
    : /OPR\/|Opera/.test(ua) ? 'opera' : /Firefox|FxiOS/.test(ua) ? 'firefox'
    : /Chrome|CriOS/.test(ua) ? 'chrome' : /Safari/.test(ua) ? 'safari' : 'other';
  var standalone = (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
  var OS_NAME = { ios: 'آیفون یا آیپد', android: 'اندروید', windows: 'ویندوز', mac: 'مک', linux: 'لینوکس', other: 'سیستم ناشناخته' };
  var BR_NAME = { chrome: 'کروم', edge: 'اج', firefox: 'فایرفاکس', safari: 'سافاری', samsung: 'سامسونگ اینترنت', opera: 'اپرا', other: 'مرورگر ناشناخته' };

  function guide() {
    var lockStep = 'روی آیکون تنظیمات یا قفل کنار آدرس سایت بزنید.';
    if (os === 'ios') {
      if (!standalone) {
        return { steps: [
          'برنامه را با سافاری باز کنید (در کروم یا فایرفاکس آیفون این کار ممکن نیست).',
          'دکمه‌ی «اشتراک‌گذاری» (مربع با فلش رو به بالا) را بزنید.',
          'گزینه‌ی «افزودن به صفحه‌ی اصلی» (Add to Home Screen) را انتخاب و تایید کنید.',
          'برنامه را از آیکون صفحه‌ی اصلی گوشی باز کنید، به همین صفحه بیایید و «فعال‌سازی اعلان» را بزنید.'],
          note: 'اعلان در آیفون فقط با iOS نسخه‌ی ۱۶٫۴ به بعد و فقط برای برنامه‌ی اضافه‌شده به صفحه‌ی اصلی کار می‌کند.' };
      }
      return { steps: [
        'اگر هنوز اجازه نداده‌اید، «فعال‌سازی اعلان» را بزنید و گزینه‌ی Allow را انتخاب کنید.',
        'اگر قبلاً رد کرده‌اید: تنظیمات گوشی ← Notifications ← فرابخش را باز کنید و Allow Notifications را روشن کنید.',
        'حالت Focus یا «مزاحم نشوید» اعلان‌ها را بی‌صدا می‌کند.'], note: '' };
    }
    if (os === 'android') {
      var where = standalone ? 'تنظیمات گوشی ← برنامه‌ها ← فرابخش ← اعلان‌ها را روشن کنید.'
        : 'تنظیمات گوشی ← برنامه‌ها ← ' + BR_NAME[browser] + ' ← اعلان‌ها را روشن کنید.';
      if (browser === 'firefox') {
        return { steps: [lockStep, '«مجوزها» را باز کنید و اعلان‌ها را روی «اجازه» بگذارید.', 'صفحه را تازه کنید.', where], note: '' };
      }
      return { steps: [lockStep, '«مجوزها» (Permissions) ← «اعلان‌ها» را روی «اجازه» بگذارید.', 'صفحه را تازه کنید.',
        'اگر باز هم اعلان نیامد: ' + where], note: 'مسیر دقیق در هر گوشی ممکن است کمی فرق کند.' };
    }
    if (os === 'mac' && browser === 'safari') {
      return { steps: ['منوی Safari ← Settings ← Websites ← Notifications را باز کنید.',
        'سایت farabakhshtahvieh.com را روی Allow بگذارید.',
        'تنظیمات مک ← Notifications ← Safari را روشن کنید.'], note: '' };
    }
    var sys = os === 'windows' ? 'تنظیمات ویندوز ← System ← Notifications: اعلان مرورگر روشن و Focus assist خاموش باشد.'
      : os === 'mac' ? 'تنظیمات مک ← Notifications ← مرورگر را روشن کنید.'
      : 'اعلان‌های سیستم‌عامل برای مرورگر باید روشن باشد.';
    return { steps: [lockStep, '«اعلان‌ها» (Notifications) را روی «اجازه» (Allow) بگذارید.', 'صفحه را تازه کنید.',
      'اگر باز هم اعلان نیامد: ' + sys], note: '' };
  }

  function status() {
    if (!('Notification' in window)) return (os === 'ios' && !standalone) ? 'ios_install' : 'unsupported';
    return Notification.permission;
  }
  var VIEW = {
    granted: ['success', 'فعال', null],
    denied: ['error', 'مسدود', 'اعلان برای این سایت مسدود است؛ با «راهنمای فعال‌سازی» بازش کنید.'],
    'default': ['warning', 'فعال نشده', 'هنوز اجازه نداده‌اید؛ دکمه‌ی فعال‌سازی را بزنید.'],
    unsupported: ['neutral', 'پشتیبانی نمی‌شود', 'این مرورگر اعلان را پشتیبانی نمی‌کند؛ مرورگر دیگری را امتحان کنید.'],
    ios_install: ['warning', 'نیازمند نصب', 'در آیفون ابتدا باید برنامه را به صفحه‌ی اصلی اضافه کنید؛ راهنما را ببینید.']
  };

  var st = status(), v = VIEW[st] || VIEW.unsupported;
  badge.className = 'fb-badge fb-badge-' + v[0];
  badge.textContent = v[1];
  text.textContent = v[2] || (devices
    ? 'اجازه‌ی اعلان داده شده و ' + fa(devices) + ' دستگاه برای حساب شما ثبت است.'
    : 'اجازه‌ی اعلان داده شده ولی هنوز دستگاهی ثبت نشده؛ صفحه را تازه کنید و چند ثانیه صبر کنید.');
  if (st === 'default') enable.classList.remove('hidden');

  enable.addEventListener('click', function () {
    enable.disabled = true;
    Promise.resolve(Notification.requestPermission()).then(function () { window.location.reload(); },
      function () { enable.disabled = false; });
  });

  openBtn.addEventListener('click', function () {
    var g = guide();
    q('[data-guide-detected]', dlg).textContent = 'سیستم شما: ' + OS_NAME[os] + ' · ' + BR_NAME[browser] + (standalone ? ' (برنامه‌ی نصب‌شده)' : '');
    var ol = q('[data-guide-steps]', dlg);
    ol.textContent = '';
    g.steps.forEach(function (s) { var li = document.createElement('li'); li.textContent = s; ol.appendChild(li); });
    q('[data-guide-note]', dlg).textContent = g.note;
    dlg.showModal();
  });
})();