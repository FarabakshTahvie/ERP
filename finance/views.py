import io
from django.contrib.auth.decorators import login_required
from django.http import Http404, FileResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
import weasyprint

from .models import Invoice


@login_required
def invoice_detail(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or invoice.billed_party_id != party.id):
        raise Http404
    return render(request, "finance/portal_invoice.html", {"invoice": invoice})


@login_required
def invoice_pdf(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    is_staff_viewer = request.user.is_staff
    if not is_staff_viewer and (not party or invoice.billed_party_id != party.id):
        raise Http404

    html = render_to_string("finance/invoice_pdf.html", {"invoice": invoice}, request=request)
    pdf_bytes = weasyprint.HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
    
    return FileResponse(
        io.BytesIO(pdf_bytes),
        as_attachment=False,
        filename=f"{invoice.number}.pdf",
        content_type="application/pdf"
    )
