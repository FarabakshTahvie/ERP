from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from .models import Project

DURATION_HINTS = {
    range(0, 5): "معمولاً چند ساعت طول می‌کشد.",
    range(5, 17): "معمولاً یک روز کاری طول می‌کشد.",
    range(17, 49): "معمولاً دو تا سه روز کاری طول می‌کشد.",
}


def _duration_hint(hours):
    if not hours:
        return ""
    for r, text in DURATION_HINTS.items():
        if hours in r:
            return text
    return "ممکن است چند روز طول بکشد."


@login_required
def project_progress(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    party = getattr(request.user, "party", None)
    if not party or party.id not in (project.partner_id, project.owner_id):
        raise Http404

    stages = [
        {
            "title": s.client_label or s.title,
            "status": s.status,
            "hint": _duration_hint(s.step_template.estimated_duration_hours),
        }
        for s in project.stages.filter(client_visible=True).order_by("order")
    ]
    return render(request, "projects/portal_progress.html", {"project": project, "stages": stages})
