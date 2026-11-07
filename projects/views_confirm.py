from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.capabilities import can
from . import confirmations, shipping_slip
from .models import Project, ProjectFile, ProjectStage, StageConfirmation, StageKind

D = StageConfirmation.Decision
DONE_TEXT = {
    D.RECEIVED: "دریافت اقلام ثبت شد. ممنون.",
    D.NOT_RECEIVED: "عدم دریافت اقلام ثبت شد.",
    D.CONFIRMED: "تایید نصب ثبت شد. ممنون.",
}


def _conf_or_404(stage_id):
    return get_object_or_404(StageConfirmation.objects.select_related("stage__project"), stage_id=stage_id)


@login_required
@require_http_methods(["GET", "POST"])
def stage_confirmation(request, stage_id):
    conf = _conf_or_404(stage_id)
    stage, project = conf.stage, conf.stage.project
    is_owner = confirmations.is_recipient_party(request.user, project)
    if not (is_owner or can(request.user, "accounting.access")):
        raise Http404

    if request.method == "POST":
        if not is_owner:
            raise Http404
        decision = request.POST.get("decision")
        try:
            confirmations.set_decision(stage_id=stage.id, decision=decision, actor=request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("projects:portal_stage_confirmation", stage.id)
        messages.success(request, DONE_TEXT.get(decision, "پاسخ ثبت شد."))
        invoice = getattr(project, "invoice", None)
        if invoice is not None and invoice.billed_party_id == request.user.party_id:
            return redirect("finance:portal_invoice_detail", invoice.uuid)
        return redirect("home")

    if is_owner:
        confirmations.record_view(conf)
    shipping = stage.kind == StageKind.SHIPPING
    can_decide = (is_owner and project.status != Project.Status.CANCELLED
                  and stage.status == ProjectStage.Status.DONE)
    install_done = (not shipping) and conf.decision == D.CONFIRMED
    return render(request, "projects/portal_stage_confirmation.html", {
        "conf": conf, "project": project, "is_shipping": shipping, "readonly": not is_owner,
        "show_buttons": can_decide and not install_done,
        "slip": shipping_slip.slip_data(stage) if shipping else None,
        "images": [
            {"name": f.display_name, "url": reverse("projects:portal_confirmation_image", args=[stage.id, f.id])}
            for f in confirmations.install_images(stage)],
    })


@login_required
def confirmation_image(request, stage_id, file_id):
    conf = get_object_or_404(StageConfirmation.objects.select_related("stage__project"),
                             stage_id=stage_id, stage__kind__in=(StageKind.INSTALL, StageKind.SHIPPING))
    if not (confirmations.is_recipient_party(request.user, conf.stage.project)
            or can(request.user, "accounting.access")):
        raise Http404
    f = get_object_or_404(ProjectFile, pk=file_id, stage_id=stage_id, kind=ProjectFile.Kind.IMAGE)
    if not f.is_displayable_image:
        raise Http404
    response = FileResponse(f.file.open("rb"), as_attachment=False, filename=f.display_name)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
