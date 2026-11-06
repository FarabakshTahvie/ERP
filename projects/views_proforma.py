from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core.capabilities import cap_required
from . import proforma_rows as rows
from .models import Project
from .views_ops import _json


def _args(post):
    kind = post.get("kind", "")
    if kind == "service":
        return {"kind": kind, "row": rows.parse_service_row(post.get("row_json"))}
    if kind == "extra":
        return {"kind": kind, "row": rows.parse_extra_row(post.get("row_json"))}
    if kind == "fee":
        return {"kind": kind, "field": post.get("field", ""), "raw": post.get("value", "")}
    raise ValueError("نوع ردیف نامعتبر است.")


@cap_required("pricing.edit")
@require_POST
def row_preview(request, project_id):
    project = get_object_or_404(Project, pk=project_id)

    def work():
        if request.POST.get("op") == "delete":
            return rows.preview_delete(project=project, actor=request.user, kind=request.POST.get("kind", ""),
                                       pk=request.POST.get("pk"))
        return rows.preview_change(project=project, actor=request.user, **_args(request.POST))
    return _json(work)


@cap_required("pricing.edit")
@require_POST
def row_save(request, project_id):
    project = get_object_or_404(Project, pk=project_id)

    def work():
        a = _args(request.POST)
        if a["kind"] == "service":
            rows.save_service_line(project=project, actor=request.user, row=a["row"])
        elif a["kind"] == "extra":
            rows.save_extra_line(project=project, actor=request.user, row=a["row"])
        else:
            rows.set_project_field(project=project, actor=request.user, field=a["field"], raw=a["raw"])
        return {"grand_total": rows.money_text(rows.proforma_summary(project)["grand_total"])}
    return _json(work)


@cap_required("pricing.edit")
@require_POST
def row_delete(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    return _json(lambda: rows.delete_line(project=project, actor=request.user, kind=request.POST.get("kind", ""),
                                          pk=request.POST.get("pk")))
