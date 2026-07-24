from __future__ import annotations

import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_SAP_IMPORTS, require_capability
from firstbrief.sapimport.forms import ImportSelectionForm, ImportUploadForm
from firstbrief.sapimport.models import ImportBatch
from firstbrief.sapimport.services import changes_by_site, commit_import, stage_import


def _actor(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise TypeError("Authenticated user expected.")
    require_capability(request.user, MANAGE_SAP_IMPORTS)
    return request.user


@login_required
@require_GET
def index(request: HttpRequest) -> HttpResponse:
    _actor(request)
    return render(
        request,
        "sapimport/index.html",
        {
            "available": ImportBatch.objects.exclude(status=ImportBatch.Status.REJECTED),
            "errors": ImportBatch.objects.filter(status=ImportBatch.Status.REJECTED),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def upload(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    form = ImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        batch = stage_import(actor=actor, filename=uploaded.name, content=uploaded.read())
        if batch.status == ImportBatch.Status.REJECTED:
            messages.error(request, "The SAP file was rejected. Review Files in error.")
            return redirect("sapimport:index")
        return redirect("sapimport:review", batch_id=batch.pk)
    return render(request, "sapimport/upload.html", {"form": form})


def _batch(batch_id: uuid.UUID) -> ImportBatch:
    return get_object_or_404(ImportBatch.objects.prefetch_related("changes"), pk=batch_id)


@login_required
@require_GET
def review(request: HttpRequest, batch_id: uuid.UUID) -> HttpResponse:
    _actor(request)
    batch = _batch(batch_id)
    choices = [
        (str(change.pk), f"{change.action}: {change.user_id}") for change in batch.changes.all()
    ]
    form = ImportSelectionForm(
        initial={"selected": [value for value, _ in choices]}, choices=choices
    )
    return render(
        request,
        "sapimport/review.html",
        {"batch": batch, "groups": changes_by_site(batch), "form": form},
    )


@login_required
@require_POST
def commit(request: HttpRequest, batch_id: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    batch = _batch(batch_id)
    choices = [(str(change.pk), change.user_id) for change in batch.changes.all()]
    form = ImportSelectionForm(request.POST, choices=choices)
    if not form.is_valid():
        return render(
            request,
            "sapimport/review.html",
            {"batch": batch, "groups": changes_by_site(batch), "form": form},
            status=400,
        )
    commit_import(
        actor=actor,
        batch=batch,
        selected_ids={int(value) for value in form.cleaned_data["selected"]},
    )
    return render(request, "sapimport/complete.html", {"batch": _batch(batch_id)})
