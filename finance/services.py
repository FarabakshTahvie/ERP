import jdatetime
import uuid
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.db import models, transaction
from django.utils import timezone
from utils.image_utils import optimize_receipt_image
from utils.utils import separate_digits
from .models import Invoice, InvoiceLine, Payment, LedgerEntry

# روش‌هایی که مبلغشان را کارشناس از روی مدرک تایید می‌کند
PROOF_METHODS = (Payment.Method.CARD_TO_CARD, Payment.Method.RECEIPT, Payment.Method.CHEQUE)
# تصویر اجباری است
FILE_REQUIRED_METHODS = (Payment.Method.RECEIPT, Payment.Method.CHEQUE)
# حداقل یکی از «تصویر» یا «شماره پیگیری» کافی است
EITHER_PROOF_METHODS = (Payment.Method.CARD_TO_CARD,)
CUSTOMER_METHODS = (
    Payment.Method.CARD_TO_CARD, Payment.Method.RECEIPT, Payment.Method.CHEQUE, Payment.Method.CREDIT,
)
ALLOWED_RECEIPT_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "gif", "pdf")
MAX_RECEIPT_BYTES = 10 * 1024 * 1024   # مرورگرهای مدرن قبل از ارسال خودشان عکس را کوچک می‌کنند؛ این سقف بافر برای PDF و مرورگرهای قدیمی است

_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_amount(raw):
    """مبلغ تومان را از متن (با ارقام فارسی و جداکننده) به Decimal صحیح تبدیل می‌کند؛ ایراد = ValueError فارسی."""
    text = str(raw if raw is not None else "").strip().translate(_FA_TO_EN)
    text = text.replace(",", "").replace("٬", "").replace(" ", "")
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("مبلغ نامعتبر است؛ فقط عدد (به تومان) وارد کنید.")
    if not value.is_finite() or value <= 0 or value != value.to_integral_value() or value >= Decimal(10) ** 15:
        raise ValueError("مبلغ باید یک عدد صحیح و بزرگ‌تر از صفر (به تومان) باشد.")
    return value.to_integral_value()


def _validate_receipt_file(receipt_file):
    name = (getattr(receipt_file, "name", "") or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED_RECEIPT_EXTENSIONS:
        raise ValueError("فرمت فایل رسید مجاز نیست؛ عکس (JPG، PNG، WEBP) یا PDF بارگذاری کنید.")
    if receipt_file.size > MAX_RECEIPT_BYTES:
        raise ValueError("حجم فایل رسید بیشتر از ۱۰ مگابایت است.")
    return ext


def proof_error(method, *, has_file, reference=""):
    """قانون مدرک پرداخت؛ تنها منبع برای فرم مشتری، سرویس و فرم ادمین. پیام خطا یا None."""
    if method in FILE_REQUIRED_METHODS and not has_file:
        return "برای رسید واریز و چک، آپلود تصویر رسید/چک الزامی است."
    if method in EITHER_PROOF_METHODS and not has_file and not (reference or "").strip():
        return "برای کارت به کارت، حداقل یکی از «تصویر رسید» یا «شماره پیگیری» را وارد کنید."
    return None


def prepare_receipt_file(receipt_file):
    """اعتبارسنجی محتوا + بهینه‌سازی + نام تصادفی (قابل‌حدس‌نبودن آدرس فایل). ایراد = ValueError فارسی."""
    ext = _validate_receipt_file(receipt_file)
    token = uuid.uuid4().hex[:16]
    if ext == "pdf":
        head = receipt_file.read(5)
        receipt_file.seek(0)
        if head != b"%PDF-":
            raise ValueError("فایل PDF معتبر نیست.")
        receipt_file.name = f"{token}.pdf"
        return receipt_file
    prepared, changed = optimize_receipt_image(receipt_file)
    prepared.name = f"{token}.webp" if changed else f"{token}.{ext}"
    return prepared


def create_customer_payment(*, invoice, method, amount_raw="", reference_number="", note="",
                            receipt_file=None, cheque_number="", cheque_bank=""):
    """
    تنها مسیر ثبت پرداخت توسط مشتری/طرف‌حساب. هر ایرادی ValueError با پیام فارسی می‌دهد.
    مبلغ واردشده «مبلغ اعلام‌شده» است؛ مبلغ رسمی را کارشناس هنگام تایید می‌نویسد.
    """
    if method not in CUSTOMER_METHODS:
        raise ValueError("روش پرداخت معتبر انتخاب کنید.")
    reference_number = (reference_number or "").strip()
    note = (note or "").strip()

    if method == Payment.Method.CREDIT:
        if not note:
            raise ValueError("برای پرداخت اعتباری، نوشتن توضیح الزامی است.")
        receipt_file, reference_number = None, ""
    else:
        error = proof_error(method, has_file=bool(receipt_file), reference=reference_number)
        if error:
            raise ValueError(error)

    remaining = invoice.remaining_amount
    amount = parse_amount(amount_raw) if str(amount_raw or "").strip() else remaining
    if amount <= 0:
        raise ValueError("این فاکتور مانده‌ای برای پرداخت ندارد.")
    if amount > remaining:
        raise ValueError(f"مبلغ نمی‌تواند از مانده‌ی فاکتور ({separate_digits(remaining)} تومان) بیشتر باشد.")

    # جلوگیری از ثبت دوباره با دوبار کلیک یا رفرش
    if Payment.objects.filter(
        invoice=invoice, method=method, claimed_amount=amount, reference_number=reference_number,
        status=Payment.Status.PENDING, created_at__gte=timezone.now() - timedelta(seconds=60),
    ).exists():
        raise ValueError("همین پرداخت لحظاتی پیش ثبت شده است؛ وضعیت را در صفحه‌ی فاکتور ببینید.")

    kwargs = dict(
        invoice=invoice, method=method, amount=amount, claimed_amount=amount,
        reference_number=reference_number, note=note,
    )
    if receipt_file:
        kwargs["receipt_file"] = prepare_receipt_file(receipt_file)
    if method == Payment.Method.CHEQUE:
        kwargs["cheque_number"] = (cheque_number or "").strip()
        kwargs["cheque_bank"] = (cheque_bank or "").strip()
    return Payment.objects.create(**kwargs)



def _generate_invoice_number():
    year = jdatetime.date.fromgregorian(date=timezone.localdate()).year
    last = Invoice.objects.filter(number__startswith=f"INV-{year}-").order_by("-id").first()
    seq = int(last.number.split("-")[-1]) + 1 if last else 1
    return f"INV-{year}-{seq:04d}"


def _make_line(invoice, line_type, title, qty, unit_price, cost_snapshot=None):
    return InvoiceLine(
        invoice=invoice,
        line_type=line_type,
        title=title,
        qty=qty,
        unit_price=unit_price,
        cost_snapshot=cost_snapshot,
        total=qty * unit_price,
    )


def _rebuild_lines(invoice, project):
    lines = [
        _make_line(invoice, InvoiceLine.LineType.SERVICE, ps.service.name, ps.qty, ps.unit_price)
        for ps in project.services.all()
    ]
    lines += [
        _make_line(invoice, InvoiceLine.LineType.MATERIAL, pm.item.name, pm.qty, pm.unit_price, pm.item.moving_average_cost)
        for pm in project.extra_materials.all()
    ]
    if project.installation_fee:
        lines.append(_make_line(invoice, InvoiceLine.LineType.INSTALLATION, "هزینه نصب", 1, project.installation_fee))
    if project.shipping_fee:
        lines.append(_make_line(invoice, InvoiceLine.LineType.SHIPPING, "هزینه ارسال", 1, project.shipping_fee))

    # هزینه‌ی عوامل اجرایی بیرونی طبق تصمیم فعلی، داخل مازاد جمع می‌شود
    participants_cost = project.participants.aggregate(total=models.Sum("agreed_cost"))["total"] or 0
    extra_total = (project.extra_fee or 0) + participants_cost
    if extra_total:
        lines.append(_make_line(invoice, InvoiceLine.LineType.EXTRA, "هزینه‌های مازاد (شامل عوامل اجرایی بیرونی)", 1, extra_total))

    InvoiceLine.objects.bulk_create(lines)
    recalculate_invoice_total(invoice)


def recalculate_invoice_total(invoice):
    total = invoice.lines.aggregate(total=models.Sum("total"))["total"] or 0
    invoice.total_amount = total
    invoice.save(update_fields=["total_amount"])


@transaction.atomic
def generate_invoice_for_project(project, issue_date=None, document_type=Invoice.DocumentType.PROFORMA):
    if hasattr(project, "invoice"):
        raise ValueError("این پروژه قبلاً فاکتور دارد (هر پروژه فقط یک فاکتور دارد).")

    from projects.services import resolve_billing_party
    invoice = Invoice.objects.create(
        project=project,
        number=_generate_invoice_number(),
        document_type=document_type,
        billed_party=resolve_billing_party(project),
        address_snapshot=project.location.address_text if project.location else "",
        contract_date=project.contract_date,
        issue_date=issue_date or timezone.localdate(),
    )
    _rebuild_lines(invoice, project)
    return invoice


@transaction.atomic
def refresh_invoice_lines(invoice):
    if invoice.document_type != Invoice.DocumentType.PROFORMA:
        raise ValueError("فقط پیش‌فاکتور قابل بازتولید ردیف‌هاست؛ فاکتور نهایی قفل است.")
    invoice.lines.filter(is_manual=False).delete()
    _rebuild_lines(invoice, invoice.project)


@transaction.atomic
def add_manual_invoice_line(invoice, title, amount, actor, line_type=InvoiceLine.LineType.EXTRA):
    """برای افزودن هزینه‌ی جدید بعد از قفل‌شدن فاکتور (تغییر طرح، کار اضافه و ...)
    بدون دست‌زدن به ردیف‌های قبلی."""
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("امکان افزودن ردیف به فاکتور لغوشده وجود ندارد.")
    line = InvoiceLine.objects.create(
        invoice=invoice, line_type=line_type, title=title, qty=1, unit_price=amount, total=amount, is_manual=True,
    )
    recalculate_invoice_total(invoice)
    return line


@transaction.atomic
def approve_payment(payment, approved_by, verified_amount=None):
    """
    فقط پرداخت «در انتظار» قابل تایید است. برای روش‌های دارای رسید، مبلغ واقعی (verified_amount)
    اجباری است و جای مبلغ اعلامی مشتری می‌نشیند. برای اعتباری نیازی به مبلغ نیست.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != Payment.Status.PENDING:
        raise ValueError("این پرداخت قبلاً بررسی شده است.")
    invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)   # جلوی تایید هم‌زمان دو پرداخت
    payment.invoice = invoice

    if payment.method in PROOF_METHODS:
        if verified_amount is None or str(verified_amount).strip() == "":
            raise ValueError("مبلغ واقعی را از روی رسید وارد کنید.")
        amount = parse_amount(verified_amount)
        remaining = invoice.remaining_amount
        if amount > remaining:
            raise ValueError(
                f"مبلغ وارد‌شده از مانده‌ی فاکتور ({separate_digits(remaining)} تومان) بیشتر است. "
                "اگر مشتری بیشتر واریز کرده، موضوع را با مدیر در میان بگذارید."
            )
        if payment.claimed_amount is None:
            payment.claimed_amount = payment.amount
        payment.amount = amount

    payment.status = Payment.Status.APPROVED
    payment.approved_by = approved_by
    payment.approved_at = timezone.now()
    payment.save()
    return payment


@transaction.atomic
def reject_payment(payment, rejected_by, reason=""):
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("برای رد پرداخت، ذکر دلیل اجباری است.")
    payment = Payment.objects.select_for_update().select_related("invoice").get(pk=payment.pk)
    if payment.status != Payment.Status.PENDING:
        raise ValueError("این پرداخت قبلاً بررسی شده است.")
    payment.status = Payment.Status.REJECTED
    payment.approved_by = rejected_by
    payment.approved_at = timezone.now()
    payment.note = (payment.note + "\n" if payment.note else "") + f"رد شد: {reason}"
    payment.save()
    return payment


def recalculate_invoice_paid_amount(invoice):
    real_paid = invoice.payments.filter(
        status=Payment.Status.APPROVED,
    ).exclude(method=Payment.Method.CREDIT).aggregate(total=models.Sum('amount'))['total'] or 0

    invoice.paid_amount = real_paid
    if invoice.total_amount > 0 and invoice.paid_amount >= invoice.total_amount:
        invoice.status = Invoice.Status.PAID
        if not invoice.settled_at:
            invoice.settled_at = timezone.now()
    elif invoice.paid_amount > 0:
        invoice.status = Invoice.Status.PARTIALLY_PAID
    invoice.save(update_fields=["paid_amount", "status", "settled_at"])


@transaction.atomic
def ensure_billed_party_account(invoice):
    """
    اگر طرف‌حساب حساب کاربری نداشت، یکی می‌سازد.
    اگر شماره موبایل طرف‌حساب از قبل متعلق به یک کاربر دیگر است (مثلاً یک تکنسین یا مدیر)،
    دیگر تلاش نمی‌کند حساب تکراری بسازد (که چون phone_number/username یکتا هستند کرش می‌داد)؛
    در عوض یا همان حساب را (اگر واقعاً مال همین طرف‌حساب/بدون طرف‌حساب و نقشش مشتری/شریک است) وصل می‌کند،
    یا در تعارض واقعی (کاربر پرسنل/مدیر) دست نمی‌زند و (None, None) برمی‌گرداند تا فراخوان تصمیم بگیرد.
    """
    from accounts.models import User
    from utils.utils import generate_random_code
    party = invoice.billed_party
    user = party.users.first()
    if user:
        return user, None

    if party.phone_number:
        existing_by_phone = User.objects.filter(phone_number=party.phone_number).first()
        if existing_by_phone:
            if existing_by_phone.party_id in (None, party.id) and existing_by_phone.role in (User.Role.CLIENT, User.Role.PARTNER):
                existing_by_phone.party = party
                existing_by_phone.save(update_fields=["party"])
                return existing_by_phone, None
            # تعارض واقعی: این شماره متعلق به حساب دیگری (مثلاً پرسنل) است؛ دست‌کاری نمی‌شود.
            return None, None

    raw_password = generate_random_code(length=10, digits_only=False)
    role = User.Role.PARTNER if party.is_partner else User.Role.CLIENT
    username = party.phone_number or f"party{party.id}"
    name_parts = (party.name or "").strip().split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    user = User.objects.create(
        username=username, role=role, phone_number=party.phone_number, party=party,
        first_name=first_name, last_name=last_name,
    )
    user.set_password(raw_password)
    user.must_change_password = False
    user.save()
    return user, raw_password


def notify_invoice_issued(invoice, user, raw_password):
    from notifications.services import create_notification
    from notifications.models import NotificationType
    create_notification(
        notification_type=NotificationType.INVOICE_ISSUED, user=user,
        title="پیش‌فاکتور شما صادر شد", body=f"پیش‌فاکتور شماره {invoice.number} صادر شد.",
        real_target_url=f"/portal/invoices/{invoice.uuid}/",
        extra_data={"invoice_number": invoice.number, "username": user.username, "password": raw_password or ""},
    )


def ensure_billed_party_account_and_notify(invoice):
    user, raw_password = ensure_billed_party_account(invoice)
    if user:
        notify_invoice_issued(invoice, user, raw_password)
    return user, raw_password
