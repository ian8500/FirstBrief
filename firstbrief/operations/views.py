"""Responsive operational dashboard and secure consumption endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, has_capability
from firstbrief.messaging.models import FileAsset
from firstbrief.operations.forms import (
    CloseMessageForm,
    FeedbackForm,
    OperationalPolicyForm,
    OtherMessageCloseForm,
)
from firstbrief.operations.models import MessageReceipt, OperationalPolicy
from firstbrief.operations.services import (
    accessible_message,
    close_message_view,
    dashboard_data,
    email_message_to_self,
    is_mandatory,
    message_rows,
    open_message_view,
    record_print,
    submit_feedback,
    update_policy,
)


def _actor(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied
    return request.user


def _session_key(request: HttpRequest) -> str:
    if request.session.session_key is None:
        request.session.create()
    return request.session.session_key or ""


def _previous_login(request: HttpRequest, actor: User) -> datetime:
    value = request.session.get("previous_login_at")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                return parsed
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=UTC)


def _site_timezone() -> ZoneInfo:
    return ZoneInfo(settings.SITE_TIME_ZONE)


@login_required
@require_GET
def dashboard(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    context = dashboard_data(actor, _previous_login(request, actor))
    context["site_timezone"] = _site_timezone()
    return render(request, "operations/dashboard.html", context)


@login_required
@require_GET
def message_list(request: HttpRequest, list_kind: str) -> HttpResponse:
    if list_kind not in {"mandatory", "other"}:
        raise Http404
    actor = _actor(request)
    sort = request.GET.get("sort", "effective")
    if sort not in {"message", "effective", "expires", "printed", "emailed"}:
        sort = "effective"
    rows = message_rows(actor, list_kind=list_kind, sort=sort)
    grouped = request.GET.get("group") == "subtype"
    groups: dict[str, dict[str, Any]] = {}
    if grouped:
        for row in rows:
            label = row.message.subtype.name if row.message.subtype else "Uncategorised"
            group = groups.setdefault(label, {"rows": [], "unread": 0})
            group_rows = group["rows"]
            if isinstance(group_rows, list):
                group_rows.append(row)
            if row.unread:
                group["unread"] += 1
    return render(
        request,
        "operations/message_list.html",
        {
            "list_kind": list_kind,
            "heading": "Mandatory Messages" if list_kind == "mandatory" else "Other Messages",
            "rows": rows,
            "grouped_rows": groups,
            "grouped": grouped,
            "sort": sort,
            "site_timezone": _site_timezone(),
            "policy": OperationalPolicy.load(),
        },
    )


@login_required
@require_GET
def message_viewer(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    session_key = _session_key(request)
    view_session = open_message_view(
        actor=actor,
        message=message,
        browser_session_key=session_key,
    )
    accessed = request.session.get("accessed_messages", [])
    label = f"{message.message_id} — {message.current_version.title}"
    if label not in accessed:
        accessed.append(label)
        request.session["accessed_messages"] = accessed
    mandatory = is_mandatory(message)
    close_form = (
        CloseMessageForm(initial={"view_session": view_session.pk, "active_seconds": 0})
        if mandatory
        else OtherMessageCloseForm(initial={"view_session": view_session.pk, "active_seconds": 0})
    )
    receipt = MessageReceipt.objects.filter(user=actor, message=message).first()
    display_asset = message.current_version.files.filter(
        role=FileAsset.Role.DISPLAY,
        scan_status=FileAsset.ScanStatus.CLEAN,
    ).first()
    return render(
        request,
        "operations/message_viewer.html",
        {
            "message": message,
            "version": message.current_version,
            "mandatory": mandatory,
            "close_form": close_form,
            "view_session": view_session,
            "receipt": receipt,
            "display_asset": display_asset,
            "policy": OperationalPolicy.load(),
            "site_timezone": _site_timezone(),
        },
    )


@login_required
@require_POST
def close_message(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    mandatory = is_mandatory(message)
    form: CloseMessageForm | OtherMessageCloseForm
    form = CloseMessageForm(request.POST) if mandatory else OtherMessageCloseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The message could not be closed. Please try again.")
        return redirect("operations:viewer", message_pk=message.pk)
    clear = mandatory and form.cleaned_data.get("action") == CloseMessageForm.Action.CLEAR
    try:
        close_message_view(
            actor=actor,
            message=message,
            view_session_id=form.cleaned_data["view_session"],
            active_seconds=form.cleaned_data["active_seconds"],
            clear=clear,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("operations:viewer", message_pk=message.pk)
    messages.success(
        request,
        "Message read and cleared." if clear else "Message marked as read.",
    )
    return redirect("operations:other" if clear or not mandatory else "operations:mandatory")


@login_required
@require_POST
def print_message(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    record_print(
        actor=actor,
        message=message,
        browser_session_key=_session_key(request),
    )
    print_asset = message.current_version.files.filter(
        role=FileAsset.Role.PRINT,
        scan_status=FileAsset.ScanStatus.CLEAN,
    ).first()
    return render(
        request,
        "operations/print_message.html",
        {
            "message": message,
            "version": message.current_version,
            "print_asset": print_asset,
            "site_timezone": _site_timezone(),
        },
    )


@login_required
@require_POST
def email_message(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    try:
        email_message_to_self(
            actor=actor,
            message=message,
            browser_session_key=_session_key(request),
            secure_url=request.build_absolute_uri(f"/operational/messages/{message.pk}/"),
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "The message has been queued for email to your profile address.")
    return redirect("operations:viewer", message_pk=message.pk)


@login_required
@require_http_methods(["GET", "POST"])
def feedback(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    form = FeedbackForm(
        request.POST or None,
        initial={
            "subject": f"Feedback on {message.message_id}",
            "body": (f"Message: {message.message_id}\nTitle: {message.current_version.title}\n\n"),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            submit_feedback(
                actor=actor,
                message=message,
                subject=form.cleaned_data["subject"],
                body=form.cleaned_data["body"],
                browser_session_key=_session_key(request),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Feedback has been queued for delivery.")
            return redirect("operations:viewer", message_pk=message.pk)
    return render(
        request,
        "operations/feedback.html",
        {"form": form, "message": message},
    )


@login_required
@xframe_options_sameorigin
@require_GET
def protected_file(
    request: HttpRequest,
    message_pk: uuid.UUID,
    asset_pk: uuid.UUID,
) -> FileResponse:
    actor = _actor(request)
    message = accessible_message(actor, message_pk)
    try:
        asset = message.current_version.files.get(
            pk=asset_pk,
            scan_status=FileAsset.ScanStatus.CLEAN,
        )
    except FileAsset.DoesNotExist as exc:
        raise Http404 from exc
    handle = default_storage.open(asset.storage_key, "rb")
    response = FileResponse(handle, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{message.message_id}-{asset.role}.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def settings_view(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    if not has_capability(actor, MANAGE_CONFIGURATION):
        raise PermissionDenied
    policy = OperationalPolicy.load()
    form = OperationalPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        update_policy(actor=actor, policy=form.save(commit=False))
        messages.success(request, "Operational dashboard policy updated.")
        return redirect("operations:settings")
    return render(request, "operations/settings.html", {"form": form})
