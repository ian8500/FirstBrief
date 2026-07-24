"""Leak-resistant scoped queries, suggestions and maintenance action policy."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone

from firstbrief.identity.models import User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    MANAGE_MESSAGES,
    has_capability,
    visible_users_for,
)
from firstbrief.messaging.models import Message, MessageVersion
from firstbrief.operations.models import MessageReceipt
from firstbrief.operations.services import accessible_messages


@dataclass(frozen=True)
class SearchRow:
    message: Message
    version: MessageVersion
    read_status: str


@dataclass(frozen=True)
class MaintenanceRow:
    message: Message
    version: MessageVersion
    actions: tuple[str, ...]


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=ZoneInfo(settings.SITE_TIME_ZONE))


def _day_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=ZoneInfo(settings.SITE_TIME_ZONE))


def _published_messages(actor: User) -> QuerySet[Message]:
    return accessible_messages(actor).filter(
        status__in=(
            Message.Status.RELEASED_PENDING_EFFECTIVE,
            Message.Status.EFFECTIVE,
            Message.Status.EXPIRED,
            Message.Status.ARCHIVED,
        )
    )


def search_messages(actor: User, criteria: dict[str, Any]) -> QuerySet[Message]:
    """Return a stable, fully scoped queryset; filters are applied only after scope."""
    receipt = MessageReceipt.objects.filter(user=actor, message_id=OuterRef("pk"))
    queryset = _published_messages(actor).annotate(
        search_read=Exists(receipt.filter(first_read_at__isnull=False)),
        search_cleared=Exists(receipt.filter(cleared_at__isnull=False)),
    )
    current = Q(versions__version_number=F("current_version_number"))
    message_id = criteria.get("message_id")
    if message_id:
        queryset = queryset.filter(message_id__icontains=message_id)
    for field in ("kind", "status"):
        value = criteria.get(field)
        if value:
            queryset = queryset.filter(**{field: value})
    for field in ("title", "summary", "content"):
        value = criteria.get(field)
        if value:
            version_field = "searchable_content" if field == "content" else field
            queryset = queryset.filter(current, **{f"versions__{version_field}__icontains": value})
    group = criteria.get("group")
    if group:
        queryset = queryset.filter(audience_rights__message_group_id=int(group))
    subtype = criteria.get("subtype")
    if subtype:
        queryset = queryset.filter(subtype_id=int(subtype))
    read_status = criteria.get("read_status")
    if read_status == "unread":
        queryset = queryset.filter(search_read=False)
    elif read_status == "read":
        queryset = queryset.filter(search_read=True)
    elif read_status == "cleared":
        queryset = queryset.filter(search_cleared=True)
    for prefix in ("release", "effective", "expiry"):
        start = criteria.get(f"{prefix}_from")
        end = criteria.get(f"{prefix}_to")
        version_field = f"versions__{prefix}_at"
        if start:
            queryset = queryset.filter(current, **{f"{version_field}__gte": _day_start(start)})
        if end:
            queryset = queryset.filter(current, **{f"{version_field}__lte": _day_end(end)})
    if not criteria.get("include_archived"):
        queryset = queryset.exclude(status=Message.Status.ARCHIVED)
    if not criteria.get("include_future"):
        queryset = queryset.filter(
            current,
            versions__release_at__lte=timezone.now(),
        ).filter(
            Q(versions__effective_at__isnull=True) | Q(versions__effective_at__lte=timezone.now())
        )
    sort_fields = {
        "message_id": "message_id",
        "title": "versions__title",
        "release": "versions__release_at",
        "effective": "versions__effective_at",
        "expiry": "versions__expiry_at",
        "status": "status",
    }
    sort_key = criteria.get("sort")
    sort = sort_fields.get(sort_key if isinstance(sort_key, str) else "", "message_id")
    direction = "-" if criteria.get("direction") == "desc" else ""
    if sort.startswith("versions__"):
        queryset = queryset.filter(current)
    return queryset.order_by(f"{direction}{sort}", f"{direction}message_id", "pk").distinct()


def search_message(actor: User, message_pk: uuid.UUID) -> Message:
    try:
        return _published_messages(actor).get(pk=message_pk)
    except Message.DoesNotExist as exc:
        raise PermissionDenied("You do not have access to this message.") from exc


def rows_for(messages: Iterable[Message], actor: User) -> list[SearchRow]:
    materialized = list(messages)
    versions = {
        (version.message_id, version.version_number): version
        for version in MessageVersion.objects.filter(
            message_id__in=[message.pk for message in materialized]
        )
    }
    receipts = {
        receipt.message_id: receipt
        for receipt in MessageReceipt.objects.filter(
            user=actor, message_id__in=[message.pk for message in materialized]
        )
    }
    rows: list[SearchRow] = []
    for message in materialized:
        receipt = receipts.get(message.pk)
        read_status = (
            "Read & Cleared"
            if receipt and receipt.cleared_at
            else "Read"
            if receipt and receipt.first_read_at
            else "Unread"
        )
        rows.append(
            SearchRow(
                message=message,
                version=versions[(message.pk, message.current_version_number)],
                read_status=read_status,
            )
        )
    return rows


def maintenance_rows(messages: Iterable[Message], actor: User) -> list[MaintenanceRow]:
    materialized = list(messages)
    versions = {
        (version.message_id, version.version_number): version
        for version in MessageVersion.objects.filter(
            message_id__in=[message.pk for message in materialized]
        )
    }
    return [
        MaintenanceRow(
            message=message,
            version=versions[(message.pk, message.current_version_number)],
            actions=permitted_maintenance_actions(actor, message),
        )
        for message in materialized
    ]


def message_suggestions(actor: User, term: str, *, limit: int = 12) -> list[dict[str, str]]:
    if len(term.strip()) < 3:
        return []
    queryset = search_messages(
        actor,
        {
            "message_id": term.strip(),
            "include_archived": True,
            "include_future": True,
            "sort": "message_id",
        },
    )[:limit]
    rows = rows_for(queryset, actor)
    return [
        {
            "value": row.message.message_id,
            "label": f"{row.message.message_id} — {row.version.title}",
        }
        for row in rows
    ]


def user_suggestions(actor: User, term: str, *, limit: int = 12) -> list[dict[str, str]]:
    term = term.strip()
    if len(term) < 3:
        return []
    users = (
        visible_users_for(actor)
        .filter(
            Q(username__istartswith=term)
            | Q(first_name__istartswith=term)
            | Q(last_name__istartswith=term)
        )
        .order_by("first_name", "last_name", "username", "pk")[:limit]
    )
    return [
        {
            "value": user.username,
            "label": f"{user.first_name}, {user.last_name} ({user.username})",
        }
        for user in users
    ]


def permitted_maintenance_actions(actor: User, message: Message) -> tuple[str, ...]:
    actions: list[str] = []
    if has_capability(actor, MANAGE_MESSAGES):
        actions.append("edit")
    if message.status == Message.Status.DRAFT and has_capability(actor, APPROVE_MESSAGES):
        actions.append("approve")
    if (
        message.status == Message.Status.APPROVED_PENDING_RELEASE
        and has_capability(actor, APPROVE_MESSAGES)
        and message.current_version.release_at > timezone.now()
    ):
        actions.append("unapprove")
    if has_capability(actor, MANAGE_MESSAGES):
        if message.status in {
            Message.Status.APPROVED_PENDING_RELEASE,
            Message.Status.RELEASED_PENDING_EFFECTIVE,
        }:
            actions.append("withdraw")
        if message.status in {
            Message.Status.RELEASED_PENDING_EFFECTIVE,
            Message.Status.EFFECTIVE,
        }:
            actions.append("cancel")
        if message.status == Message.Status.ARCHIVED:
            actions.append("restore")
    return tuple(actions)
