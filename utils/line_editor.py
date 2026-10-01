import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
BAD = "اطلاعات ردیف‌ها نامعتبر است؛ صفحه را دوباره باز کنید."


@dataclass(frozen=True)
class Col:
    key: str
    label: str
    type: str = "text"        # picker | number | money | text | checkbox | select
    required: bool = True
    positive: bool = False    # فقط number/money: باید > 0 باشد
    max_len: int = 255
    choices: tuple = ()       # فقط select


def _pk(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _to_decimal(raw, col):
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace("٫", ".")
    if not text:
        if col.required:
            raise ValueError(f"«{col.label}» را وارد کنید.")
        return None
    if "e" in text.lower():
        raise ValueError(f"«{col.label}» نامعتبر است؛ فقط عدد وارد کنید.")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError(f"«{col.label}» نامعتبر است؛ فقط عدد وارد کنید.")
    if not value.is_finite() or value < 0 or (col.positive and value == 0):
        raise ValueError(f"«{col.label}» باید عددی {'بزرگ‌تر از صفر' if col.positive else 'نامنفی'} باشد.")
    if col.type == "money" and value != value.to_integral_value():
        raise ValueError(f"«{col.label}» باید عدد صحیح (تومان) باشد.")
    if value >= Decimal(10) ** 12:
        raise ValueError(f"«{col.label}» بیش از حد بزرگ است.")
    return value


def parse_row(raw, columns):
    if not isinstance(raw, dict):
        raise ValueError(BAD)
    out = {"pk": _pk(raw.get("pk"))}
    for col in columns:
        value = raw.get(col.key)
        if col.type == "picker":
            try:
                out[col.key] = int(value)
            except (TypeError, ValueError):
                if col.required:
                    raise ValueError(f"«{col.label}» را انتخاب کنید.")
                out[col.key] = None
        elif col.type in ("number", "money"):
            out[col.key] = _to_decimal(value, col)
        elif col.type == "checkbox":
            out[col.key] = value is True or value in ("1", 1, "true", "on")
        elif col.type == "select":
            value = str(value or "")
            if col.required and value not in col.choices:
                raise ValueError(f"«{col.label}» معتبر انتخاب کنید.")
            if not col.required and value and value not in col.choices:
                raise ValueError(f"«{col.label}» معتبر انتخاب کنید.")
            out[col.key] = value if value in col.choices else None
        else:
            text = str(value or "").strip()
            if not text and col.required:
                raise ValueError(f"«{col.label}» را وارد کنید.")
            if len(text) > col.max_len:
                raise ValueError(f"«{col.label}» بیش از حد طولانی است.")
            out[col.key] = text
    return out


def parse_rows(raw_json, columns, *, children_key=None, children_columns=(), max_rows=200, max_children=100):
    """None = ارسال نشده (دست نزن). JSON خراب یا ردیف نامعتبر = ValueError فارسی."""
    if raw_json is None:
        return None
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        raise ValueError(BAD)
    if not isinstance(data, list):
        raise ValueError(BAD)
    if len(data) > max_rows:
        raise ValueError(f"حداکثر {max_rows} ردیف مجاز است.")
    rows = []
    for raw in data:
        row = parse_row(raw, columns)
        if children_key:
            kids = raw.get(children_key) or []
            if not isinstance(kids, list) or len(kids) > max_children:
                raise ValueError(BAD)
            row[children_key] = [parse_row(k, children_columns) for k in kids]
        rows.append(row)
    return rows
