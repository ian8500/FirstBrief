from __future__ import annotations

import uuid

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from firstbrief.assurance.models import AuditEvent, LegalHold, PurgeRun, RetentionPolicy
from firstbrief.assurance.services import (
    approve_and_execute_purge,
    continuity_export,
    preview_purge,
)
from firstbrief.identity.models import User
from firstbrief.identity.services import (
    MANAGE_RETENTION,
    VIEW_AUDIT_HISTORY,
    require_capability,
)


def _actor(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise TypeError("Authenticated user expected.")
    return request.user


@login_required
@require_GET
def audit(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    require_capability(actor, VIEW_AUDIT_HISTORY)
    events = AuditEvent.objects.select_related("actor")
    if request.GET.get("action"):
        events = events.filter(action__icontains=request.GET["action"])
    if request.GET.get("object_id"):
        events = events.filter(object_id__icontains=request.GET["object_id"])
    return render(
        request,
        "assurance/audit.html",
        {"page": Paginator(events, 50).get_page(request.GET.get("page"))},
    )


@login_required
@require_http_methods(["GET", "POST"])
def retention(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    require_capability(actor, MANAGE_RETENTION)
    if request.method == "POST":
        preview_purge(actor)
        return redirect("assurance:retention")
    return render(
        request,
        "assurance/retention.html",
        {
            "policy": RetentionPolicy.load(),
            "runs": PurgeRun.objects.select_related("requested_by", "approved_by")[:20],
            "holds": LegalHold.objects.filter(active=True).select_related("message"),
        },
    )


@login_required
@require_POST
def approve_purge(request: HttpRequest, run_id: uuid.UUID) -> HttpResponse:
    approve_and_execute_purge(_actor(request), get_object_or_404(PurgeRun, pk=run_id))
    return redirect("assurance:retention")


@login_required
@require_GET
def continuity(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    require_capability(actor, MANAGE_RETENTION)
    payload, digest = continuity_export()
    response = HttpResponse(payload, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="firstbrief-continuity.json"'
    response["X-Content-SHA256"] = digest
    response["Cache-Control"] = "private, no-store"
    return response
