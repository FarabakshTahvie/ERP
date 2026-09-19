from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.contrib import messages
from unfold.decorators import display, action
from simple_history.admin import SimpleHistoryAdmin
from .models import Invoice, InvoiceLine, Payment, LedgerEntry
from .services import refresh_invoice_lines, approve_payment, add_manual_invoice_line
from .forms import AddInvoiceLineForm


class InvoiceLineInline(TabularInline):
    model = InvoiceLine
    extra = 0
    readonly_fields = ('total',)


class PaymentInline(TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('approved_by', 'approved_at')

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for payment in instances:
            if payment.status == Payment.Status.APPROVED and not payment.approved_by_id:
                payment.approved_by = request.user
                payment.approved_at = timezone.now()
            payment.save()
        formset.save_m2m()


@admin.register(Invoice)
class InvoiceAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ('number', 'project', 'billed_party', 'document_type', 'status_badge', 'total_amount', 'paid_amount', 'issue_date')
    list_filter = ('document_type', 'status', 'issue_date')
    search_fields = ('number', 'project__name', 'billed_party__name')
    raw_id_fields = ('project', 'billed_party')
    readonly_fields = ('number', 'total_amount', 'paid_amount', 'uuid', 'settled_at')
    inlines = [InvoiceLineInline, PaymentInline]
    actions = ['action_refresh_lines', 'action_mark_final', 'action_add_manual_line', 'action_issue_credentials']

    def has_module_permission(self, request):
        return request.user.is_superuser or getattr(request.user, "role", None) == "manager"

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    @display(
        description="وضعیت فاکتور",
        label={
            Invoice.Status.DRAFT: "info",
            Invoice.Status.SENT: "warning",
            Invoice.Status.AWAITING_APPROVAL: "warning",
            Invoice.Status.PARTIALLY_PAID: "warning",
            Invoice.Status.PAID: "success",
            Invoice.Status.CANCELLED: "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="تبدیل به فاکتور نهایی (قفل ردیف‌ها)")
    def action_mark_final(self, request, queryset):
        count = queryset.update(document_type=Invoice.DocumentType.FINAL)
        self.message_user(request, f"{count} فاکتور به حالت نهایی در آمدند.")

    @action(description="افزودن هزینه‌ی جدید (بعد از قفل‌شدن فاکتور)", dialog={"title": "افزودن هزینه جدید", "description": "عنوان و مبلغ هزینه را وارد کنید.", "form_class": AddInvoiceLineForm})
    def action_add_manual_line(self, request, form, object_id):
        invoice = Invoice.objects.get(pk=object_id)
        title = form.cleaned_data["title"]
        amount = form.cleaned_data["amount"]
        try:
            add_manual_invoice_line(invoice, title=title, amount=amount, actor=request.user)
            messages.success(request, f"هزینه به فاکتور {invoice.number} اضافه شد.")
        except ValueError as e:
            messages.error(request, str(e))
        return HttpResponse(headers={"HX-Redirect": reverse_lazy("admin:finance_invoice_changelist")})

    @admin.action(description="بازتولید ردیف‌ها از پروژه (فقط پیش‌نویس)")
    def action_refresh_lines(self, request, queryset):
        for invoice in queryset:
            try:
                refresh_invoice_lines(invoice)
            except ValueError as e:
                self.message_user(request, str(e), level='error')

    @admin.action(description="ساخت حساب و آماده‌سازی اطلاع‌رسانی برای طرف‌حساب")
    def action_issue_credentials(self, request, queryset):
        from .services import ensure_billed_party_account_and_notify
        for invoice in queryset:
            user, raw_password = ensure_billed_party_account_and_notify(invoice)
            msg = f"{invoice.number}: یوزرنیم {user.username}"
            if raw_password:
                msg += f" / پسورد {raw_password}"
            self.message_user(request, msg)


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ('id', 'invoice', 'method', 'amount', 'status_badge', 'paid_at')
    list_filter = ('method', 'status')
    search_fields = ('invoice__number', 'reference_number', 'cheque_number')
    actions = ['action_approve']

    def has_module_permission(self, request):
        return request.user.is_superuser or getattr(request.user, "role", None) == "manager"

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    @display(
        description="وضعیت پرداخت",
        label={
            Payment.Status.PENDING: "warning",
            Payment.Status.APPROVED: "success",
            Payment.Status.REJECTED: "danger",
        }
    )
    def status_badge(self, obj):
        return obj.status

    @admin.action(description="تایید پرداخت‌های انتخاب‌شده")
    def action_approve(self, request, queryset):
        for payment in queryset.exclude(status=Payment.Status.APPROVED):
            approve_payment(payment, approved_by=request.user)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ModelAdmin):
    list_display = ('id', 'party', 'entry_type', 'amount', 'description', 'created_at')
    list_filter = ('entry_type',)
    search_fields = ('party__name', 'description')

    def has_module_permission(self, request):
        return request.user.is_superuser or getattr(request.user, "role", None) == "manager"

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)
