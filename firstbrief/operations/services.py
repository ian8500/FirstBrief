"""Scoped operational queries and auditable message-consumption commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.template.loader import render_to_string
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, MANAGE_MESSAGES, require_capability
from firstbrief.messaging.models import Message, MessageAudienceRight
from firstbrief.notifications.models import NotificationJob, NotificationPolicy
from firstbrief.notifications.services import apply_quiet_hours
from firstbrief.operations.models import (
    MessageAccessEvent,
    MessageReceipt,
    MessageViewSession,
    OperationalPolicy,
)


@dataclass(frozen=True)
class MessageRow:
    message: Message
    mandatory: bool
    unread: bool
    cleared: bool
    forthcoming: bool
    overdue: bool
    printed_at: datetime | None
    emailed_at: datetime | None
    effective_at: datetime


def _audience_annotations(
    queryset: QuerySet[Message], group_ids: list[int] | None
) -> QuerySet[Message]:
    rights = MessageAudienceRight.objects.filter(message_id=OuterRef("pk"))
    if group_ids is not None:
        rights = rights.filter(message_group_id__in=group_ids)
    return queryset.annotate(
        audience_prohibited=Exists(rights.filter(right=MessageAudienceRight.Right.PROHIBITED)),
        audience_allowed=Exists(
            rights.filter(
                right__in=(
                    MessageAudienceRight.Right.ALLOWED,
                    MessageAudienceRight.Right.MANDATORY,
                )
            )
        ),
        audience_mandatory=Exists(rights.filter(right=MessageAudienceRight.Right.MANDATORY)),
    )


def accessible_messages(user: User) -> QuerySet[Message]:
    queryset = Message.objects.select_related(
        "message_type", "subtype", "originator"
    ).prefetch_related("audience_rights__message_group")
    if user.is_superuser:
        return _audience_annotations(queryset, None).filter(  # type: ignore[misc]
            audience_allowed=True
        )
    if not user.site_id:
        return queryset.none()
    group_ids = list(user.message_groups.values_list("pk", flat=True))
    if not group_ids:
        return queryset.none()
    permitted_types = user.roles.filter(is_active=True).values_list("message_types__pk", flat=True)
    return (
        _audience_annotations(queryset, group_ids)
        .filter(
            message_type_id__in=permitted_types,
            audience_allowed=True,
            audience_prohibited=False,
            audience_rights__message_group__primary_group__site_id=user.site_id,
        )
        .distinct()
    )


def operational_messages(user: User) -> QuerySet[Message]:
    policy = OperationalPolicy.load()
    forthcoming_cutoff = timezone.now() + timedelta(hours=policy.pre_effective_hours)
    return (
        accessible_messages(user)
        .filter(
            Q(status=Message.Status.EFFECTIVE)
            | Q(
                status=Message.Status.RELEASED_PENDING_EFFECTIVE,
                versions__version_number=F("current_version_number"),
                versions__effective_at__lte=forthcoming_cutoff,
            )
        )
        .distinct()
    )


def accessible_message(user: User, message_pk: uuid.UUID) -> Message:
    try:
        return operational_messages(user).get(pk=message_pk)
    except Message.DoesNotExist as exc:
        raise PermissionDenied("You do not have access to this message.") from exc


def is_mandatory(message: Message) -> bool:
    return bool(getattr(message, "audience_mandatory", False))


def message_rows(
    user: User,
    *,
    list_kind: str,
    sort: str = "effective",
) -> list[MessageRow]:
    now = timezone.now()
    messages = list(operational_messages(user))
    receipts = {
        receipt.message_id: receipt
        for receipt in MessageReceipt.objects.filter(
            user=user, message_id__in=[message.pk for message in messages]
        )
    }
    rows: list[MessageRow] = []
    for message in messages:
        receipt = receipts.get(message.pk)
        mandatory = is_mandatory(message)
        cleared = bool(receipt and receipt.cleared_at)
        if list_kind == "mandatory" and (not mandatory or cleared):
            continue
        if list_kind == "other" and mandatory and not cleared:
            continue
        version = message.current_version
        effective_at = version.effective_at or version.release_at
        unread = not receipt or not receipt.first_read_at
        forthcoming = message.status == Message.Status.RELEASED_PENDING_EFFECTIVE
        rows.append(
            MessageRow(
                message=message,
                mandatory=mandatory,
                unread=unread,
                cleared=cleared,
                forthcoming=forthcoming,
                overdue=mandatory and unread and effective_at <= now,
                printed_at=receipt.printed_at if receipt else None,
                emailed_at=receipt.emailed_at if receipt else None,
                effective_at=effective_at,
            )
        )
    sorters = {
        "message": lambda row: row.message.message_id.casefold(),
        "effective": lambda row: row.effective_at,
        "expires": lambda row: row.message.current_version.expiry_at,
        "printed": lambda row: row.printed_at or datetime.min.replace(tzinfo=UTC),
        "emailed": lambda row: row.emailed_at or datetime.min.replace(tzinfo=UTC),
    }
    rows.sort(key=sorters.get(sort, sorters["effective"]))
    return rows


def dashboard_data(user: User, previous_login_at: datetime) -> dict[str, Any]:
    now = timezone.now()
    policy = OperationalPolicy.load()
    all_messages = operational_messages(user)
    effective_since: list[Message] = []
    forthcoming: list[Message] = []
    botd: list[Message] = []
    for message in all_messages:
        version = message.current_version
        effective_at = version.effective_at or version.release_at
        mandatory = is_mandatory(message)
        if (
            mandatory
            and message.status == Message.Status.EFFECTIVE
            and previous_login_at <= effective_at <= now
        ):
            effective_since.append(message)
        if (
            message.status == Message.Status.RELEASED_PENDING_EFFECTIVE
            and effective_at <= now + timedelta(hours=policy.pre_effective_hours)
        ):
            forthcoming.append(message)
        if message.kind == Message.Kind.BOTD and message.status == Message.Status.EFFECTIVE:
            if (
                user.is_superuser
                or not user.default_message_group_id
                or message.audience_rights.filter(message_group_id=user.default_message_group_id)
                .exclude(right=MessageAudienceRight.Right.PROHIBITED)
                .exists()
            ):
                botd.append(message)
    return {
        "effective_since": sorted(
            effective_since,
            key=lambda message: (
                message.current_version.effective_at or message.current_version.release_at
            ),
            reverse=True,
        ),
        "forthcoming": sorted(
            forthcoming,
            key=lambda message: (
                message.current_version.effective_at or message.current_version.release_at
            ),
        ),
        "botd": sorted(botd, key=lambda message: message.current_version.release_at),
        "mandatory_unread": sum(
            1 for row in message_rows(user, list_kind="mandatory") if row.unread
        ),
        "other_unread": sum(1 for row in message_rows(user, list_kind="other") if row.unread),
        "policy": policy,
    }


@transaction.atomic
def open_message_view(
    *,
    actor: User,
    message: Message,
    browser_session_key: str,
) -> MessageViewSession:
    now = timezone.now()
    receipt, _ = MessageReceipt.objects.select_for_update().get_or_create(
        user=actor, message=message
    )
    receipt.last_accessed_at = now
    receipt.save(update_fields=("last_accessed_at",))
    view_session = MessageViewSession.objects.create(
        user=actor,
        message=message,
        browser_session_key=browser_session_key,
    )
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=MessageAccessEvent.EventType.OPENED,
        browser_session_key=browser_session_key,
    )
    record_event("message.opened", actor=actor, subject=message)
    return view_session


@transaction.atomic
def close_message_view(
    *,
    actor: User,
    message: Message,
    view_session_id: uuid.UUID,
    active_seconds: int,
    clear: bool,
) -> MessageReceipt:
    now = timezone.now()
    try:
        view_session = MessageViewSession.objects.select_for_update().get(
            pk=view_session_id,
            user=actor,
            message=message,
            closed_at__isnull=True,
        )
    except MessageViewSession.DoesNotExist as exc:
        raise ValidationError("This viewing session is no longer active.") from exc
    elapsed = max(0, int((now - view_session.opened_at).total_seconds()) + 5)
    credited = min(max(active_seconds, 0), elapsed, 14_400)
    view_session.active_seconds = credited
    view_session.closed_at = now
    view_session.save(update_fields=("active_seconds", "closed_at"))

    receipt, _ = MessageReceipt.objects.select_for_update().get_or_create(
        user=actor, message=message
    )
    if receipt.first_read_at is None:
        receipt.first_read_at = now
    if clear:
        if not is_mandatory(message):
            raise ValidationError("Only mandatory messages can be read and cleared.")
        receipt.cleared_at = now
    receipt.cumulative_view_seconds += credited
    receipt.last_accessed_at = now
    receipt.save(
        update_fields=(
            "first_read_at",
            "cleared_at",
            "cumulative_view_seconds",
            "last_accessed_at",
        )
    )
    event_type = (
        MessageAccessEvent.EventType.CLEARED if clear else MessageAccessEvent.EventType.READ
    )
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=event_type,
        browser_session_key=view_session.browser_session_key,
        duration_seconds=credited,
    )
    record_event(
        f"message.{event_type}",
        actor=actor,
        subject=message,
        after={"viewing_seconds": credited, "acknowledged": clear},
    )
    return receipt


def _record_action(
    *,
    actor: User,
    message: Message,
    event_type: str,
    browser_session_key: str,
) -> MessageReceipt:
    now = timezone.now()
    receipt, _ = MessageReceipt.objects.get_or_create(user=actor, message=message)
    fields = ["last_accessed_at"]
    receipt.last_accessed_at = now
    if event_type == MessageAccessEvent.EventType.PRINTED:
        receipt.printed_at = now
        fields.append("printed_at")
    elif event_type == MessageAccessEvent.EventType.EMAILED:
        receipt.emailed_at = now
        fields.append("emailed_at")
    receipt.save(update_fields=fields)
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=event_type,
        browser_session_key=browser_session_key,
    )
    record_event(f"message.{event_type}", actor=actor, subject=message)
    return receipt


@transaction.atomic
def record_print(*, actor: User, message: Message, browser_session_key: str) -> MessageReceipt:
    return _record_action(
        actor=actor,
        message=message,
        event_type=MessageAccessEvent.EventType.PRINTED,
        browser_session_key=browser_session_key,
    )


def _queue_user_notification(
    *,
    message: Message,
    kind: str,
    recipients: list[str],
    subject: str,
    body: str,
) -> NotificationJob:
    now = timezone.now()
    scheduled = apply_quiet_hours(now, NotificationPolicy.load())
    return NotificationJob.objects.create(
        message=message,
        kind=kind,
        recipients=sorted({value.casefold() for value in recipients if value}),
        subject=subject,
        body=body,
        deduplication_key=f"{kind}:{message.pk}:{uuid.uuid4()}",
        scheduled_at=scheduled,
        next_attempt_at=scheduled,
    )


@transaction.atomic
def email_message_to_self(
    *,
    actor: User,
    message: Message,
    browser_session_key: str,
    secure_url: str,
) -> NotificationJob:
    if not actor.email:
        raise ValidationError("Your profile does not contain an email address.")
    version = message.current_version
    context = {"message": message, "version": version, "secure_url": secure_url}
    job = _queue_user_notification(
        message=message,
        kind=NotificationJob.Kind.MESSAGE_TO_SELF,
        recipients=[actor.email],
        subject=" ".join(
            render_to_string("operations/email/message_to_self_subject.txt", context).splitlines()
        ).strip(),
        body=render_to_string("operations/email/message_to_self_body.txt", context).strip(),
    )
    _record_action(
        actor=actor,
        message=message,
        event_type=MessageAccessEvent.EventType.EMAILED,
        browser_session_key=browser_session_key,
    )
    return job


@transaction.atomic
def submit_feedback(
    *,
    actor: User,
    message: Message,
    subject: str,
    body: str,
    browser_session_key: str,
) -> NotificationJob:
    recipients = list(
        User.objects.filter(
            Q(is_superuser=True)
            | Q(direct_capabilities__codename=MANAGE_MESSAGES)
            | Q(roles__capabilities__codename=MANAGE_MESSAGES)
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if message.originator.email:
        recipients.append(message.originator.email)
    if not recipients:
        raise ValidationError("No feedback recipient is configured.")
    version = message.current_version
    context = {
        "message": message,
        "version": version,
        "actor": actor,
        "feedback_subject": subject,
        "feedback_body": body,
    }
    job = _queue_user_notification(
        message=message,
        kind=NotificationJob.Kind.FEEDBACK,
        recipients=recipients,
        subject=" ".join(
            render_to_string("operations/email/feedback_subject.txt", context).splitlines()
        ).strip(),
        body=render_to_string("operations/email/feedback_body.txt", context).strip(),
    )
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=MessageAccessEvent.EventType.FEEDBACK,
        browser_session_key=browser_session_key,
        metadata={"subject": subject},
    )
    record_event(
        "message.feedback",
        actor=actor,
        subject=message,
        after={"notification_job": job.pk},
    )
    return job


def update_policy(*, actor: User, policy: OperationalPolicy) -> OperationalPolicy:
    require_capability(actor, MANAGE_CONFIGURATION)
    policy.full_clean()
    policy.save()
    record_event(
        "operations.policy.updated",
        actor=actor,
        subject=policy,
        after={
            "pre_effective_hours": policy.pre_effective_hours,
            "pre_effective_colour": policy.pre_effective_colour,
            "idle_timeout_seconds": policy.idle_timeout_seconds,
        },
    )
    return policy
