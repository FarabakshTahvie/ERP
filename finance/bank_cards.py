import re

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_JUNK = re.compile(r"[\s\-\u200c]")

# کلید: (نام فارسی، رنگ شروع گرادیان، رنگ پایان)
BANKS = {
    "melli": ("ملی ایران", "#14407a", "#2f7fc1"),
    "mellat": ("ملت", "#8f1d21", "#d8453b"),
    "saderat": ("صادرات ایران", "#0b3a6f", "#1d8fd1"),
    "tejarat": ("تجارت", "#1d3f91", "#4a7be0"),
    "sepah": ("سپه", "#9a4a12", "#d17a1f"),
    "refah": ("رفاه کارگران", "#0f5757", "#25a597"),
    "keshavarzi": ("کشاورزی", "#1b5a2c", "#4da766"),
    "maskan": ("مسکن", "#a8481a", "#d4892a"),
    "parsian": ("پارسیان", "#741230", "#c63f5d"),
    "pasargad": ("پاسارگاد", "#6b4a0a", "#b5851c"),
    "saman": ("سامان", "#17488a", "#38a3e6"),
    "sina": ("سینا", "#2b4a9c", "#5a80d6"),
    "shahr": ("شهر", "#9c1a30", "#e2566e"),
    "dey": ("دی", "#393d8c", "#6a70d6"),
    "ayandeh": ("آینده", "#612a66", "#c065b3"),
    "post": ("پست بانک", "#17653a", "#58b97c"),
    "mehr": ("مهر ایران", "#7a4a0c", "#d9a228"),
    "resalat": ("رسالت", "#0d5c75", "#38a9c9"),
    "karafarin": ("کارآفرین", "#4a2f7a", "#8b6bd1"),
    "other": ("سایر بانکها", "#2f3b4d", "#64748b"),
}
BANK_CHOICES = [(key, spec[0]) for key, spec in BANKS.items()]


def normalize_card(raw):
    return _JUNK.sub("", str(raw or "").translate(_FA_DIGITS))


def normalize_sheba(raw):
    text = _JUNK.sub("", str(raw or "").translate(_FA_DIGITS)).upper()
    if re.fullmatch(r"\d{24}", text):
        text = "IR" + text
    return text


def is_valid_card(number):
    """۱۶ رقم، الگوریتم Luhn (کارتهای بانکی ایران هم همیناند)، و نه همهی ارقام یکسان."""
    if not re.fullmatch(r"\d{16}", number or "") or len(set(number)) == 1:
        return False
    total = 0
    for i, ch in enumerate(number):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def is_valid_sheba(value):
    """IR + ۲۴ رقم؛ رقم کنترلی ISO 7064 (باقیماندهی ۹۷ برابر ۱)."""
    if not re.fullmatch(r"IR\d{24}", value or ""):
        return False
    return int(value[4:] + "1827" + value[2:4]) % 97 == 1


def normalize_cvv2(raw):
    return _JUNK.sub("", str(raw or "").translate(_FA_DIGITS))


def normalize_expiry(raw):
    """«۰۵/۰۸»، «0508»، «05-08» ← «05/08» (سال/ماه، همان ترتیب روی کارت). نامعتبر همان متن تمیزشده برمی‌گردد تا اعتبارسنجی ردش کند."""
    text = _JUNK.sub("", str(raw or "").translate(_FA_DIGITS)).replace("/", "")
    return f"{text[:2]}/{text[2:]}" if re.fullmatch(r"\d{4}", text) else text


def is_valid_cvv2(value):
    return bool(re.fullmatch(r"\d{3,4}", value or ""))


def is_valid_expiry(value):
    return bool(re.fullmatch(r"\d{2}/(0[1-9]|1[0-2])", value or ""))


def logo_url(key):
    """آدرس آیکون بانک از static/banks/<key>.svg|png|webp؛ فایل نبود ← رشتهی خالی."""
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static
    for ext in ("svg", "png", "webp"):
        path = f"banks/{key}.{ext}"
        if finders.find(path):
            return static(path)
    return ""
