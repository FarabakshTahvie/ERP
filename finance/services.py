from django.db import models, transaction
from django.utils import timezone
from .models import Invoice, InvoiceLine, Payment, LedgerEntry


def _generate_invoice_number():
    year = timezone.now().strftime("%y")
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

    invoice = Invoice.objects.create(
        project=project,
        number=_generate_invoice_number(),
        document_type=document_type,
        billed_party=project.partner,
        address_snapshot=project.location.address_text if project.location else "",
        contract_date=project.contract_date,
        issue_date=issue_date or timezone.now().date(),
    )
    _rebuild_lines(invoice, project)
    return invoice


@transaction.atomic
def refresh_invoice_lines(invoice):
    if invoice.document_type != Invoice.DocumentType.PROFORMA:
        raise ValueError("فقط پیش‌فاکتور قابل بازتولید ردیف‌هاست؛ فاکتور نهایی قفل است.")
    invoice.lines.all().delete()
    _rebuild_lines(invoice, invoice.project)


@transaction.atomic
def add_manual_invoice_line(invoice, title, amount, actor, line_type=InvoiceLine.LineType.EXTRA):
    """برای افزودن هزینه‌ی جدید بعد از قفل‌شدن فاکتور (تغییر طرح، کار اضافه و ...)
    بدون دست‌زدن به ردیف‌های قبلی."""
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("امکان افزودن ردیف به فاکتور لغوشده وجود ندارد.")
    line = InvoiceLine.objects.create(
        invoice=invoice, line_type=line_type, title=title, qty=1, unit_price=amount, total=amount,
    )
    recalculate_invoice_total(invoice)
    return line


@transaction.atomic
def approve_payment(payment, approved_by):
    payment.status = Payment.Status.APPROVED
    payment.approved_by = approved_by
    payment.approved_at = timezone.now()
    payment.save()
    # توجه: دیگر LedgerEntry خودکار برای روش اعتباری ساخته نمی‌شود چون
    # Invoice.remaining_amount و Party.total_outstanding خودشان این بدهی را نشان می‌دهند.
    # LedgerEntry فقط برای ثبت دستی موارد خارج از چارچوب فاکتور (مثل تسویه‌ی قدیمی) استفاده می‌شود.


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
def ensure_billed_party_account_and_notify(invoice):
    """
    وقتی پیش‌فاکتور صادر می‌شود: اگر طرف‌حساب فاکتور کاربر لاگین‌کننده ندارد، یکی می‌سازیم.
    ارسال پیامک/پوش حاوی یوزرنیم/پسورد/لینک فعلاً کامنت است.
    """
    from accounts.models import User
    from utils.utils import generate_random_code

    party = invoice.billed_party
    user = party.users.first()
    raw_password = None

    if not user:
        raw_password = generate_random_code(length=10, digits_only=False)
        role = User.Role.PARTNER if party.is_partner else User.Role.CLIENT
        username = party.phone_number or f"party{party.id}"
        user = User.objects.create(username=username, role=role, phone_number=party.phone_number, party=party)
        user.set_password(raw_password)
        user.must_change_password = True
        user.save()

    # TODO(پیامک/پوش صدور پیش‌فاکتور): بعد از تایید نهایی محتوا و پترن sms.ir از کامنت خارج شود.
    # از پترن آماده‌ی "invoice_issued_with_credentials" در notifications/sms_patterns.py استفاده کن.
    # from notifications.services import create_notification
    # from notifications.models import NotificationType
    # create_notification(
    #     notification_type=NotificationType.INVOICE_ISSUED,
    #     user=user,
    #     title="پیش‌فاکتور شما صادر شد",
    #     body=f"پیش‌فاکتور شماره {invoice.number} صادر شد.",
    #     real_target_url=f"/portal/invoices/{invoice.uuid}/",
    #     extra_data={
    #         "invoice_number": invoice.number,
    #         "username": user.username,
    #         "password": raw_password or "",
    #     },
    # )

    return user, raw_password
