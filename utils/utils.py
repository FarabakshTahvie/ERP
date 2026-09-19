import os
import secrets
import string
import uuid
import re
from pathlib import Path
from django.core.exceptions import ValidationError
from django.utils.text import slugify


def separate_digits(amount):
    """
    Separates a number into 3-digit comma-separated format.
    Example: 1500000 -> "1,500,000"
    """
    if amount is None:
        return ""
    try:
        val = int(amount)
        return f"{val:,}"
    except (ValueError, TypeError):
        return str(amount)


def rial_to_toman(amount_in_rial):
    """
    Converts Rials to Toman (divides by 10).
    Example: 10000 -> 1000
    """
    if amount_in_rial is None:
        return 0
    try:
        return int(amount_in_rial) // 10
    except (ValueError, TypeError):
        return 0


def format_price(amount, currency="toman", is_rial_input=False):
    """
    Formats price with 3-digit comma separation and optional currency label.
    If is_rial_input=True and currency='toman', converts Rials to Toman first.
    """
    if amount is None:
        return "0"

    try:
        val = int(amount)
        if is_rial_input and currency.lower() in ["toman", "تومان"]:
            val = val // 10

        formatted = f"{val:,}"
        if currency:
            return f"{formatted} {currency}"
        return formatted
    except (ValueError, TypeError):
        return str(amount)


def generate_random_code(length=6, digits_only=True, prefix=""):
    """
    Generates a cryptographically secure random unique code.
    Suitable for invoice numbers, tracking IDs, and OTPs.

    :param length: Length of the generated code (excluding prefix)
    :param digits_only: If True, uses 0-9. If False, uses uppercase alphanumeric.
    :param prefix: Optional string prefix (e.g., 'INV-')
    """
    if digits_only:
        alphabet = string.digits
    else:
        alphabet = string.ascii_uppercase + string.digits

    code = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}{code}"


def is_valid_national_code(code):
    """
    Validates Iranian National Code (کد ملی) checksum algorithm.
    Returns True if valid, False otherwise.
    """
    if not code or not isinstance(code, str):
        return False

    # Must be exactly 10 digits and numeric
    if not re.match(r'^\d{10}$', code):
        return False

    # Check for repetitive invalid patterns (e.g., '0000000000', '1111111111', etc.)
    if code == code[0] * 10:
        return False

    try:
        check_digit = int(code[9])
        total = sum(int(code[i]) * (10 - i) for i in range(9))
        remainder = total % 11

        if remainder < 2:
            return check_digit == remainder
        else:
            return check_digit == (11 - remainder)
    except (ValueError, TypeError):
        return False


def validate_national_code(value):
    """
    Django validator for Iranian National Code.
    """
    if not is_valid_national_code(value):
        raise ValidationError("کد ملی وارد شده معتبر نمی‌باشد (فرمت یا رقم کنترلی اشتباه است).")


def sanitize_filename(instance, filename, upload_to_path="uploads/"):
    """
    File Upload Sanitizer & Hasher for Django FileField/ImageField upload_to.

    Prevents duplicate names, malicious characters, and long filenames while preserving
    file extensions (such as .dwg, .pdf, .png, .docx, .xlsx, etc.).

    Structure: <upload_to_path>/<clean_stem>_<random_hash>.<ext>
    """
    path = Path(filename)
    extension = path.suffix.lower()  # Preserves extensions like .dwg, .pdf, etc.
    stem = path.stem

    # Sanitize and slugify original file stem (keep Persian or ASCII characters safely)
    clean_stem = re.sub(r'[^\w\s-]', '', stem).strip()
    clean_stem = re.sub(r'[-\s]+', '-', clean_stem)

    # Truncate clean stem to avoid max path length issues
    if len(clean_stem) > 30:
        clean_stem = clean_stem[:30]

    if not clean_stem:
        clean_stem = "file"

    # Generate a unique short UUID hex (8 chars)
    unique_hash = uuid.uuid4().hex[:8]

    new_filename = f"{clean_stem}_{unique_hash}{extension}"

    # Organize by path if provided
    return os.path.join(upload_to_path, new_filename)
