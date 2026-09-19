from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from .models import Invoice


@login_required
def invoice_detail(request, invoice_uuid):
    invoice = get_object_or_404(Invoice, uuid=invoice_uuid)
    party = getattr(request.user, "party", None)
    if not party or invoice.billed_party_id != party.id:
        raise Http404
    return render(request, "finance/portal_invoice.html", {"invoice": invoice})
