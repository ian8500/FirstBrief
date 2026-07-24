"""Accessible search, scoped suggestions and bounded export endpoints."""

from __future__ import annotations

import csv
import uuid

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import User
from firstbrief.messaging.models import FileAsset
from firstbrief.retrieval.forms import MessageSearchForm
from firstbrief.retrieval.services import (
    message_suggestions,
    rows_for,
    search_message,
    search_messages,
    user_suggestions,
)


def _actor(request: HttpRequest) -> User:
    user = request.user
    if not isinstance(user, User):
        raise TypeError("Authenticated user is not a FirstBrief user.")
    return user


def _criteria(request: HttpRequest, actor: User) -> tuple[MessageSearchForm, dict[str, object]]:
    form = MessageSearchForm(request.GET or None, actor=actor)
    return form, form.cleaned_data if form.is_valid() else {}


@login_required
@require_GET
def search(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    form, criteria = _criteria(request, actor)
    queryset = search_messages(actor, criteria) if form.is_valid() else search_messages(actor, {})
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "retrieval/search.html",
        {
            "form": form,
            "page": page,
            "rows": rows_for(page.object_list, actor),
            "querystring": query.urlencode(),
        },
    )


@login_required
@require_GET
def suggest_messages(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"results": message_suggestions(_actor(request), request.GET.get("q", ""))})


@login_required
@require_GET
def suggest_users(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"results": user_suggestions(_actor(request), request.GET.get("q", ""))})


@login_required
@require_GET
def message_detail(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = search_message(actor, message_pk)
    version = message.current_version
    display_asset = version.files.filter(
        role=FileAsset.Role.DISPLAY,
        scan_status=FileAsset.ScanStatus.CLEAN,
    ).first()
    record_event("message.search.opened", actor=actor, subject=message)
    return render(
        request,
        "retrieval/message.html",
        {"message": message, "version": version, "display_asset": display_asset},
    )


@login_required
@xframe_options_sameorigin
@require_GET
def protected_file(
    request: HttpRequest,
    message_pk: uuid.UUID,
    asset_pk: uuid.UUID,
) -> FileResponse:
    message = search_message(_actor(request), message_pk)
    try:
        asset = message.current_version.files.get(
            pk=asset_pk,
            scan_status=FileAsset.ScanStatus.CLEAN,
        )
    except FileAsset.DoesNotExist as exc:
        raise Http404 from exc
    response = FileResponse(
        default_storage.open(asset.storage_key, "rb"), content_type="application/pdf"
    )
    response["Content-Disposition"] = f'inline; filename="{message.message_id}-{asset.role}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


def _safe_csv(value: object) -> str:
    text = str(value or "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


@login_required
@require_GET
def export_csv(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    form, criteria = _criteria(request, actor)
    queryset = search_messages(actor, criteria) if form.is_valid() else search_messages(actor, {})
    rows = rows_for(queryset[:5000], actor)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="firstbrief-search.csv"'
    response["Cache-Control"] = "private, no-store"
    writer = csv.writer(response)
    writer.writerow(("Message ID", "Kind", "Title", "Summary", "Subtype", "Status", "Read status"))
    for row in rows:
        writer.writerow(
            _safe_csv(value)
            for value in (
                row.message.message_id,
                row.message.get_kind_display(),
                row.version.title,
                row.version.summary,
                row.message.subtype or "",
                row.message.get_status_display(),
                row.read_status,
            )
        )
    record_event(
        "message.search.exported",
        actor=actor,
        after={"row_count": len(rows), "filters": sorted(criteria)},
    )
    return response
