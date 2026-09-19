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
    if invoice.status != Invoice.Status.DRAFT:
        raise ValueError("فقط فاکتورهای پیش‌نویس قابل بازتولید ردیف‌ها هستند.")
    invoice.lines.all().delete()
    _rebuild_lines(invoice, invoice.project)


@transaction.atomic
def approve_payment(payment, approved_by):
    payment.status = Payment.Status.APPROVED
    payment.approved_by = approved_by
    payment.approved_at = timezone.now()
    payment.save()

    if payment.method == Payment.Method.CREDIT:
        LedgerEntry.objects.create(
            party=payment.invoice.billed_party,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount=payment.amount,
            description=f"اعتباری بابت فاکتور {payment.invoice.number}",
            related_object=payment,
        )


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
