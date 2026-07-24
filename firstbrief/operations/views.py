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
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, has_capability
from firstbrief.messaging.models import FileAsset
from firstbrief.operations.forms import (
    CloseMessageForm,
    DashboardPreferenceForm,
    FeedbackForm,
    OperationalPolicyForm,
    OtherMessageCloseForm,
)
from firstbrief.operations.models import DashboardPreference, MessageReceipt, OperationalPolicy
from firstbrief.operations.pdf import pdf_navigation
from firstbrief.operations.services import (
    accessible_message,
    accessible_messages,
    active_session_message,
    adjacent_mandatory_messages,
    close_message_view,
    dashboard_data,
    email_message_to_self,
    is_mandatory,
    message_rows,
    open_message_view,
    operational_messages,
    record_print,
    related_messages,
    save_reading_position,
    submit_feedback,
    update_policy,
    version_change_summary,
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
    version = message.current_version
    session_key = _session_key(request)
    view_session = open_message_view(
        actor=actor,
        message=message,
        browser_session_key=session_key,
    )
    accessed = request.session.get("accessed_messages", [])
    label = f"{message.message_id} — {version.title}"
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
    display_asset = version.files.filter(
        role=FileAsset.Role.DISPLAY,
        scan_status=FileAsset.ScanStatus.CLEAN,
    ).first()
    navigation = pdf_navigation(display_asset) if display_asset else None
    position = (
        actor.reading_positions.filter(message=message, version=version).first()
        if display_asset
        else None
    )
    previous_mandatory, next_mandatory = adjacent_mandatory_messages(actor, message)
    operational_scope = operational_messages(actor)
    supersedes = (
        operational_scope.filter(pk=message.supersedes_id).first()
        if message.supersedes_id
        else None
    )
    superseded_by_pk = getattr(message, "superseded_by", None)
    superseded_by = (
        operational_scope.filter(pk=superseded_by_pk.pk).first()
        if superseded_by_pk
        else None
    )
    related = related_messages(actor, message)
    related_items = [
        {
            "message": related_message,
            "version": next(
                version
                for version in related_message.versions.all()
                if version.version_number == related_message.current_version_number
            ),
        }
        for related_message in related
    ]
    response = render(
        request,
        "operations/message_viewer.html",
        {
            "message": message,
            "version": version,
            "mandatory": mandatory,
            "close_form": close_form,
            "view_session": view_session,
            "receipt": receipt,
            "display_asset": display_asset,
            "pdf_navigation": navigation,
            "pdf_pages_json": (
                [
                    {
                        "page": page.page,
                        "label": page.label,
                        "excerpt": page.excerpt,
                        "text": page.text,
                    }
                    for page in navigation.pages
                ]
                if navigation
                else []
            ),
            "secure_pdf_url": (
                reverse(
                    "operations:file",
                    kwargs={"message_pk": message.pk, "asset_pk": display_asset.pk},
                )
                if display_asset
                else ""
            ),
            "last_page": position.page if position else 1,
            "previous_mandatory": previous_mandatory,
            "next_mandatory": next_mandatory,
            "related_items": related_items,
            "supersedes": supersedes,
            "superseded_by": superseded_by,
            "version_changes": version_change_summary(message),
            "policy": OperationalPolicy.load(),
            "site_timezone": _site_timezone(),
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def close_message(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = _actor(request)
    raw_session = request.POST.get("view_session", "")
    try:
        session_id = uuid.UUID(raw_session)
    except (TypeError, ValueError):
        raise PermissionDenied from None
    message, view_session = active_session_message(
        actor=actor,
        message_pk=message_pk,
        view_session_id=session_id,
    )
    mandatory = view_session.mandatory_at_open
    form: CloseMessageForm | OtherMessageCloseForm
    form = CloseMessageForm(request.POST) if mandatory else OtherMessageCloseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The message could not be closed. Please try again.")
        return redirect("operations:viewer", message_pk=message.pk)
    clear_requested = mandatory and form.cleaned_data.get("action") == CloseMessageForm.Action.CLEAR
    current_access = accessible_messages(actor).filter(pk=message.pk).first()
    session_version_number = view_session.version.version_number if view_session.version else 0
    lifecycle_current = bool(
        current_access
        and current_access.status
        in (
            current_access.Status.EFFECTIVE,
            current_access.Status.RELEASED_PENDING_EFFECTIVE,
        )
        and current_access.current_version_number == session_version_number
    )
    can_clear_now = bool(
        lifecycle_current
        and current_access
        and is_mandatory(current_access)
        and current_access.status == current_access.Status.EFFECTIVE
    )
    acknowledgement_blocked = clear_requested and not can_clear_now
    lifecycle_changed = not lifecycle_current
    clear = clear_requested and can_clear_now
    message_for_close = current_access if current_access is not None else message
    try:
        close_message_view(
            actor=actor,
            message=message_for_close,
            view_session_id=form.cleaned_data["view_session"],
            active_seconds=form.cleaned_data["active_seconds"],
            clear=clear,
            lifecycle_changed=lifecycle_changed or acknowledgement_blocked,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("operations:viewer", message_pk=message.pk)
    if lifecycle_changed or acknowledgement_blocked:
        messages.warning(
            request,
            "Reading time was recorded, but acknowledgement was not accepted because "
            "the message changed, expired or was cancelled while open.",
        )
    else:
        messages.success(
            request,
            "Message acknowledged and cleared." if clear else "Message marked as read.",
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
@require_POST
def reading_position(request: HttpRequest, message_pk: uuid.UUID) -> JsonResponse:
    actor = _actor(request)
    try:
        session_id = uuid.UUID(request.POST.get("view_session", ""))
        page = int(request.POST.get("page", "1"))
        total_pages = int(request.POST.get("total_pages", "1"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid reading position."}, status=400)
    message, _ = active_session_message(
        actor=actor,
        message_pk=message_pk,
        view_session_id=session_id,
    )
    try:
        position = save_reading_position(
            actor=actor,
            message=message,
            view_session_id=session_id,
            page=page,
            total_pages=total_pages,
        )
    except ValidationError as exc:
        return JsonResponse({"error": "; ".join(exc.messages)}, status=400)
    response = JsonResponse(
        {
            "page": position.page,
            "total_pages": position.total_pages,
            "progress": round(position.page / position.total_pages * 100),
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_GET
def viewer_status(request: HttpRequest, message_pk: uuid.UUID) -> JsonResponse:
    actor = _actor(request)
    try:
        session_id = uuid.UUID(request.GET.get("view_session", ""))
    except (TypeError, ValueError):
        raise PermissionDenied from None
    message, session = active_session_message(
        actor=actor,
        message_pk=message_pk,
        view_session_id=session_id,
    )
    current_access = accessible_messages(actor).filter(pk=message.pk).first()
    version_changed = bool(
        session.version_id
        and session.version
        and session.version.version_number != message.current_version_number
    )
    lifecycle_changed = bool(
        current_access is None
        or message.status
        not in (
            message.Status.EFFECTIVE,
            message.Status.RELEASED_PENDING_EFFECTIVE,
        )
        or version_changed
    )
    can_clear = bool(
        current_access
        and session.mandatory_at_open
        and is_mandatory(current_access)
        and current_access.status == current_access.Status.EFFECTIVE
        and session.version_id == current_access.current_version.pk
    )
    response = JsonResponse(
        {
            "status": message.status,
            "status_label": message.get_status_display(),
            "can_clear": can_clear,
            "mandatory_at_open": session.mandatory_at_open,
            "lifecycle_changed": lifecycle_changed,
            "version_changed": version_changed,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def settings_view(request: HttpRequest) -> HttpResponse:
    actor = _actor(request)
    preference = DashboardPreference.load_for(actor)
    policy = OperationalPolicy.load()
    can_manage_policy = has_capability(actor, MANAGE_CONFIGURATION)
    preference_form = DashboardPreferenceForm(
        request.POST if request.method == "POST" and "save_preferences" in request.POST else None,
        instance=preference,
    )
    policy_form = OperationalPolicyForm(
        request.POST if request.method == "POST" and "save_policy" in request.POST else None,
        instance=policy,
    )
    if request.method == "POST" and "save_preferences" in request.POST:
        if preference_form.is_valid():
            preference_form.save()
            messages.success(request, "Your dashboard preferences were saved.")
            return redirect("operations:settings")
    elif request.method == "POST":
        if not can_manage_policy:
            raise PermissionDenied
        if policy_form.is_valid():
            update_policy(actor=actor, policy=policy_form.save(commit=False))
            messages.success(request, "Operational dashboard policy updated.")
            return redirect("operations:settings")
    return render(
        request,
        "operations/settings.html",
        {
            "preference_form": preference_form,
            "policy_form": policy_form,
            "can_manage_policy": can_manage_policy,
        },
    )
