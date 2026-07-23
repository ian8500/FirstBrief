"""Scoped message authoring and lifecycle administration."""

from __future__ import annotations

import uuid
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from firstbrief.configuration.models import MessageGroup, MessageSubType
from firstbrief.identity.models import User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    CREATE_MESSAGES,
    MANAGE_MESSAGES,
    SEE_ALL_PMG,
    has_capability,
)
from firstbrief.messaging.files import attach_message_pdfs
from firstbrief.messaging.forms import (
    LifecycleActionForm,
    MessageCreateForm,
    MessageRevisionForm,
)
from firstbrief.messaging.models import Message
from firstbrief.messaging.scanning import get_scanner
from firstbrief.messaging.services import (
    approve_message,
    archive_message,
    cancel_message,
    create_message,
    expire_message,
    make_effective,
    release_message,
    restore_message,
    revise_message,
    unapprove_message,
    withdraw_message,
)


def actor_for(request: HttpRequest) -> User:
    if not isinstance(request.user, User):
        raise PermissionDenied
    return request.user


def require_any_message_permission(actor: User) -> None:
    if not any(
        has_capability(actor, capability)
        for capability in (CREATE_MESSAGES, APPROVE_MESSAGES, MANAGE_MESSAGES)
    ):
        raise PermissionDenied


def scoped_messages(actor: User) -> QuerySet[Message]:
    queryset = Message.objects.select_related(
        "message_type", "subtype", "originator"
    ).prefetch_related("audience_rights__message_group")
    if actor.is_superuser or has_capability(actor, SEE_ALL_PMG):
        return queryset
    if not actor.site_id:
        return queryset.none()
    return queryset.filter(
        audience_rights__message_group__primary_group__site_id=actor.site_id
    ).distinct()


@login_required
def message_list(request: HttpRequest) -> HttpResponse:
    actor = actor_for(request)
    require_any_message_permission(actor)
    queryset = scoped_messages(actor)
    group_id = request.GET.get("group", "")
    subtype_id = request.GET.get("subtype", "")
    if group_id.isdigit():
        queryset = queryset.filter(audience_rights__message_group_id=int(group_id))
    if subtype_id.isdigit():
        queryset = queryset.filter(subtype_id=int(subtype_id))
    can_see_all = actor.is_superuser or has_capability(actor, SEE_ALL_PMG)
    groups = MessageGroup.objects.filter(is_active=True)
    subtypes = MessageSubType.objects.filter(is_active=True)
    if not can_see_all:
        site_id = actor.site_id
        if site_id is None:
            groups = groups.none()
            subtypes = subtypes.none()
        else:
            groups = groups.filter(primary_group__site_id=site_id)
            subtypes = subtypes.filter(primary_group__site_id=site_id)
    return render(
        request,
        "messaging/list.html",
        {
            "message_list": queryset,
            "groups": groups,
            "subtypes": subtypes,
            "group_id": group_id,
            "subtype_id": subtype_id,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def message_create(request: HttpRequest) -> HttpResponse:
    actor = actor_for(request)
    if not has_capability(actor, CREATE_MESSAGES):
        raise PermissionDenied
    form = MessageCreateForm(request.POST or None, request.FILES or None, actor=actor)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                message = create_message(
                    actor=actor,
                    message_id=form.cleaned_data["message_id"],
                    kind=form.cleaned_data["kind"],
                    message_type=form.cleaned_data["message_type"],
                    subtype=form.cleaned_data["subtype"],
                    title=form.cleaned_data["title"],
                    summary=form.cleaned_data["summary"],
                    text_content=form.cleaned_data["text_content"],
                    release_at=form.cleaned_data["release_at"],
                    effective_at=form.cleaned_data["effective_at"],
                    expiry_at=form.cleaned_data["expiry_at"],
                    archive_on_expiry=form.cleaned_data["archive_on_expiry"],
                    group_rights=form.group_rights(),
                    approvers=list(form.cleaned_data["approvers"]),
                )
                if message.kind == Message.Kind.INSTRUCTION:
                    attach_message_pdfs(
                        version=message.current_version,
                        display_upload=form.cleaned_data["display_pdf"],
                        print_upload=form.cleaned_data["print_pdf"],
                        actor=actor,
                        scanner=get_scanner(),
                    )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Message {message.message_id} created.")
            return redirect("messaging:detail", message_pk=message.pk)
    return render(request, "messaging/form.html", {"form": form, "heading": "Create message"})


@login_required
def message_detail(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = actor_for(request)
    require_any_message_permission(actor)
    message = get_object_or_404(scoped_messages(actor), pk=message_pk)
    return render(
        request,
        "messaging/detail.html",
        {
            "message": message,
            "version": message.current_version,
            "approve_key": uuid.uuid4(),
            "action_buttons": [
                {"command": command, "label": label, "key": uuid.uuid4()}
                for command, label in (
                    ("unapprove", "Unapprove"),
                    ("release", "Release"),
                    ("effective", "Make effective"),
                    ("expire", "Expire"),
                    ("archive", "Archive"),
                    ("withdraw", "Withdraw"),
                    ("cancel", "Cancel"),
                    ("restore", "Restore"),
                )
            ],
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def message_edit(request: HttpRequest, message_pk: uuid.UUID) -> HttpResponse:
    actor = actor_for(request)
    if not has_capability(actor, MANAGE_MESSAGES):
        raise PermissionDenied
    message = get_object_or_404(scoped_messages(actor), pk=message_pk)
    form = MessageRevisionForm(
        request.POST or None, request.FILES or None, message=message, actor=actor
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                revised = revise_message(
                    actor=actor,
                    message=message,
                    expected_version=message.lock_version,
                    title=form.cleaned_data["title"],
                    summary=form.cleaned_data["summary"],
                    text_content=form.cleaned_data["text_content"],
                    release_at=form.cleaned_data["release_at"],
                    effective_at=form.cleaned_data["effective_at"],
                    expiry_at=form.cleaned_data["expiry_at"],
                    group_rights=form.group_rights(),
                    reason=form.cleaned_data["reason"],
                )
                if revised.kind == Message.Kind.INSTRUCTION:
                    attach_message_pdfs(
                        version=revised.current_version,
                        display_upload=form.cleaned_data["display_pdf"],
                        print_upload=form.cleaned_data["print_pdf"],
                        actor=actor,
                        scanner=get_scanner(),
                    )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, f"Message {revised.message_id} revised.")
            return redirect("messaging:detail", message_pk=revised.pk)
    return render(request, "messaging/form.html", {"form": form, "heading": "Edit message"})


ACTION_MAP: dict[str, Any] = {
    "approve": approve_message,
    "unapprove": unapprove_message,
    "release": release_message,
    "effective": make_effective,
    "expire": expire_message,
    "archive": archive_message,
    "withdraw": withdraw_message,
    "cancel": cancel_message,
    "restore": restore_message,
}


@login_required
@require_http_methods(["POST"])
def message_action(request: HttpRequest, message_pk: uuid.UUID, command: str) -> HttpResponse:
    actor = actor_for(request)
    require_any_message_permission(actor)
    message = get_object_or_404(scoped_messages(actor), pk=message_pk)
    form = LifecycleActionForm(request.POST)
    action = ACTION_MAP.get(command)
    if action is None:
        raise Http404
    if form.is_valid():
        values: dict[str, Any] = {
            "actor": actor,
            "message": message,
            "expected_version": form.cleaned_data["expected_version"],
            "idempotency_key": form.cleaned_data["idempotency_key"],
        }
        if command == "approve":
            values["justification"] = form.cleaned_data["reason"]
            values["validity_justification"] = form.cleaned_data["validity_justification"]
        elif command in {"unapprove", "withdraw", "cancel"}:
            values["reason"] = form.cleaned_data["reason"]
        elif command == "restore":
            values["reason"] = form.cleaned_data["reason"]
            values["future_expiry_at"] = form.cleaned_data["future_expiry_at"]
        try:
            action(**values)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, f"Message action '{command}' completed.")
    else:
        messages.error(request, "The action request was invalid or stale.")
    return redirect("messaging:detail", message_pk=message.pk)
