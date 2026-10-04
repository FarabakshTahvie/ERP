"""
لایه‌ی قابلیت: تنها جای تعریف «چه کسی چه کاری می‌تواند».
توابع قدیمی (user_can_*، can_edit_pricing، ...) فقط پوسته‌ی نازک روی همین جدول‌اند.
قابلیت تازه = یک ردیف در CAPABILITIES + یک ردیف در تست ماتریسی (core/tests_capabilities.py).
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import Http404

SPECIALTY_ACCOUNTANT = "حسابدار"
SPECIALTY_WAREHOUSE = "انباردار"
SPECIALTY_INTAKE = "پذیرش"


class _Facts:
    """حقایق یک کاربر؛ با یک کوئری (فقط برای تکنسین) ساخته می‌شود."""
    __slots__ = ("manager", "employee", "names", "accountant")

    def __init__(self, user):
        auth = bool(user is not None and user.is_authenticated)
        role = getattr(user, "role", None) if auth else None
        self.manager = bool(auth and (user.is_superuser or role == "manager"))
        self.employee = bool(auth and role == "employee")
        self.names = set(user.specialties.values_list("name", flat=True)) if self.employee else set()
        self.accountant = SPECIALTY_ACCOUNTANT in self.names


def _manager(f):
    return f.manager


def _manager_or_accountant(f):
    return f.manager or f.accountant


CAPABILITIES = {
    # --- مدیر ---
    "dashboard.manager": _manager,
    "periods.unlock": _manager,
    "people.edit": _manager,
    "activity.view": _manager,
    "stages.assign": _manager,
    "admin.panel": _manager,
    "projects.cancel": _manager,
    "invoice.cancel": _manager,
    # --- مدیر یا حسابدار ---
    "accounting.access": _manager_or_accountant,
    "payments.review": _manager_or_accountant,
    "pricing.edit": _manager_or_accountant,
    "costs.manage": _manager_or_accountant,
    "final_review.view": _manager_or_accountant,
    "money.view": _manager_or_accountant,
    "periods.lock": _manager_or_accountant,
    "invoice.adjust": _manager_or_accountant,
    "people.view": _manager_or_accountant,
    # --- تکنسین با تخصص (مدیر عمداً نه؛ مدیر از ادمین استفاده می‌کند) ---
    "inventory.manage": lambda f: f.employee and bool(f.names & {SPECIALTY_WAREHOUSE, SPECIALTY_ACCOUNTANT}),
    "projects.create": lambda f: f.employee and bool(f.names & {SPECIALTY_INTAKE, SPECIALTY_ACCOUNTANT}),
}


def can(user, capability):
    try:
        rule = CAPABILITIES[capability]
    except KeyError:
        raise KeyError(f"قابلیت ناشناخته: {capability}")
    return bool(rule(_Facts(user)))


def capabilities_for(user):
    """همه‌ی قابلیت‌های یک کاربر با یک بار ساخت حقایق (برای تمپلیت‌ها)."""
    facts = _Facts(user)
    return {name: bool(rule(facts)) for name, rule in CAPABILITIES.items()}


def is_manager(user):
    return _Facts(user).manager


def is_accountant(user):
    return _Facts(user).accountant


def cap_required(capability):
    """ورود نکرده ← صفحه‌ی ورود؛ قابلیت ندارد ← ۴۰۴ (وجود صفحه لو نرود)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can(request.user, capability):
                raise Http404
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
