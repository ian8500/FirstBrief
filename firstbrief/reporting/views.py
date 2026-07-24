"""Authorised criteria, immutable report viewers and protected exports."""

from __future__ import annotations

import csv
import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import User
from firstbrief.identity.services import VIEW_REPORTS, require_capability
from firstbrief.reporting.catalogue import REPORT_BY_CODE, REPORTS
from firstbrief.reporting.forms import ReportCriteriaForm
from firstbrief.reporting.models import ReportRun
from firstbrief.reporting.services import (
    accessible_run,
    create_report_run,
    render_report_pdf,
    safe_csv_value,
)


def _actor(request: HttpRequest) -> User:
    user = request.user
    if not isinstance(user, User):
        raise TypeError("Authenticated user is not a FirstBrief user.")
    require_capability(user, VIEW_REPORTS)
    return user


@login_required
@require_GET
def catalogue(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    return render(
        request,
        "reporting/catalogue.html",
        {
            "reports": REPORTS,
            "recent_runs": ReportRun.objects.filter(actor=actor)[:10],
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def criteria(request: HttpRequest, report_code: str) -> HttpResponse:
    actor = _actor(request)
    definition = REPORT_BY_CODE.get(report_code.upper())
    if definition is None:
        return render(request, "error.html", {"message": "Unknown report."}, status=404)
    form = ReportCriteriaForm(request.POST or request.GET or None, actor=actor)
    if request.method == "POST" and form.is_valid():
        run = create_report_run(
            actor,
            definition.code,
            form.cleaned_data,
            force_async=bool(form.cleaned_data.get("force_async")),
        )
        return redirect("reporting:viewer", run_id=run.pk)
    return render(
        request,
        "reporting/criteria.html",
        {"definition": definition, "form": form},
    )


@login_required
@require_GET
def viewer(request: HttpRequest, run_id: uuid.UUID) -> HttpResponse:
    run = accessible_run(_actor(request), run_id)
    close_query = urlencode(
        {
            key: value
            for key, value in run.criteria.items()
            if value not in ("", None, False, []) and key != "force_async"
        },
        doseq=True,
    )
    return render(
        request,
        "reporting/viewer.html",
        {
            "run": run,
            "definition": REPORT_BY_CODE[run.report_code],
            "close_query": close_query,
        },
    )


def _complete_run(request: HttpRequest, run_id: uuid.UUID) -> tuple[User, ReportRun]:
    actor = _actor(request)
    run = accessible_run(actor, run_id)
    if run.status != ReportRun.Status.COMPLETE:
        raise ValueError("Report is not complete.")
    return actor, run


@login_required
@require_GET
def export_csv(request: HttpRequest, run_id: uuid.UUID) -> HttpResponse:
    actor, run = _complete_run(request, run_id)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{run.report_code}-{run.pk}.csv"'
    response["Cache-Control"] = "private, no-store"
    writer = csv.writer(response)
    writer.writerow(safe_csv_value(value) for value in run.columns)
    for row in run.rows:
        writer.writerow(safe_csv_value(value) for value in row)
    record_event("report.exported", actor=actor, subject=run, after={"format": "csv"})
    return response


@login_required
@require_GET
def export_pdf(request: HttpRequest, run_id: uuid.UUID) -> HttpResponse:
    actor, run = _complete_run(request, run_id)
    response = HttpResponse(render_report_pdf(run), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{run.report_code}-{run.pk}.pdf"'
    response["Cache-Control"] = "private, no-store"
    record_event("report.exported", actor=actor, subject=run, after={"format": "pdf"})
    return response
