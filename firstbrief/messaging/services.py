"""Transactional message aggregate commands and audience resolution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.configuration.models import MessageGroup
from firstbrief.identity.models import User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    CREATE_MESSAGES,
    MANAGE_MESSAGES,
    SEE_ALL_PMG,
    has_capability,
    require_capability,
)
from firstbrief.messaging.models import (
    Approval,
    FileAsset,
    LifecycleCommand,
    Message,
    MessageAudienceRight,
    MessageStatusHistory,
    MessageVersion,
)


class StaleMessageError(ValidationError):
    pass


def _replayed_command(message: Message, idempotency_key: uuid.UUID, command: str) -> Message | None:
    existing = LifecycleCommand.objects.filter(
        message=message, idempotency_key=idempotency_key
    ).first()
    if existing is None:
        return None
    if existing.command != command:
        raise ValidationError("Idempotency key was already used for another command.")
    message.refresh_from_db()
    return message


def _validate_rights(
    *, actor: User, message: Message, group_rights: dict[int, str]
) -> list[MessageAudienceRight]:
    if not group_rights:
        raise ValidationError("At least one Allowed or Mandatory audience is required.")
    valid_rights = set(MessageAudienceRight.Right.values)
    if any(right not in valid_rights for right in group_rights.values()):
        raise ValidationError("Unknown audience right.")
    if not any(
        right in {MessageAudienceRight.Right.ALLOWED, MessageAudienceRight.Right.MANDATORY}
        for right in group_rights.values()
    ):
        raise ValidationError("At least one Allowed or Mandatory audience is required.")
    groups = {group.pk: group for group in MessageGroup.objects.filter(pk__in=group_rights)}
    if len(groups) != len(group_rights):
        raise ValidationError("One or more audience groups do not exist.")
    if not actor.is_superuser and not has_capability(actor, SEE_ALL_PMG):
        if not actor.site_id or any(
            group.primary_group.site_id != actor.site_id for group in groups.values()
        ):
            raise PermissionDenied("Audience groups must belong to your site.")
    subtype = message.subtype
    if subtype is not None and subtype.primary_group_id not in {
        group.primary_group_id for group in groups.values()
    }:
        raise ValidationError(
            {"subtype": "Subtype must belong to a selected Primary Message Group."}
        )
    return [
        MessageAudienceRight(message=message, message_group=groups[group_id], right=right)
        for group_id, right in group_rights.items()
    ]


def _validate_future_dates(
    *, release_at: datetime, effective_at: datetime | None, expiry_at: datetime
) -> None:
    now = timezone.now()
    if release_at <= now:
        raise ValidationError({"release_at": "Release must be in the future when created."})
    if effective_at and effective_at <= now:
        raise ValidationError({"effective_at": "Effective time must be in the future."})
    if expiry_at <= now:
        raise ValidationError({"expiry_at": "Expiry must be in the future."})


@transaction.atomic
def create_message(
    *,
    actor: User,
    message_id: str,
    kind: str,
    message_type: Any,
    subtype: Any | None,
    title: str,
    summary: str,
    text_content: str,
    release_at: datetime,
    effective_at: datetime | None,
    expiry_at: datetime,
    archive_on_expiry: bool,
    group_rights: dict[int, str],
    approvers: list[User] | None = None,
) -> Message:
    require_capability(actor, CREATE_MESSAGES)
    _validate_future_dates(release_at=release_at, effective_at=effective_at, expiry_at=expiry_at)
    message = Message(
        message_id=message_id,
        kind=kind,
        message_type=message_type,
        subtype=subtype,
        originator=actor,
        archive_on_expiry=archive_on_expiry,
        status=(
            Message.Status.DRAFT
            if message_type.requires_approval
            else Message.Status.APPROVED_PENDING_RELEASE
        ),
    )
    message.full_clean()
    message.save()
    version = MessageVersion(
        message=message,
        version_number=1,
        title=title,
        summary=summary,
        text_content=text_content,
        searchable_content=text_content,
        release_at=release_at,
        effective_at=effective_at,
        expiry_at=expiry_at,
        created_by=actor,
    )
    version.full_clean()
    version.save()
    rights = _validate_rights(actor=actor, message=message, group_rights=group_rights)
    MessageAudienceRight.objects.bulk_create(rights)
    message.approvers.set(approvers or [])
    MessageStatusHistory.objects.create(
        message=message,
        from_status="",
        to_status=message.status,
        actor=actor,
        reason="Message created.",
        aggregate_version=message.lock_version,
    )
    record_event(
        "message.created",
        actor=actor,
        subject=message,
        after={
            "message_id": message.message_id,
            "kind": message.kind,
            "status": message.status,
        },
    )
    from firstbrief.notifications.services import register_message_created

    register_message_created(message)
    return message


def _lock_message(message: Message, expected_version: int) -> Message:
    locked = Message.objects.select_for_update().get(pk=message.pk)
    if locked.lock_version != expected_version:
        raise StaleMessageError(
            f"Message changed from version {expected_version} to {locked.lock_version}; refresh."
        )
    return locked


@transaction.atomic
def revise_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    title: str,
    summary: str,
    text_content: str,
    release_at: datetime,
    effective_at: datetime | None,
    expiry_at: datetime,
    group_rights: dict[int, str],
    reason: str,
) -> Message:
    require_capability(actor, MANAGE_MESSAGES)
    locked = _lock_message(message, expected_version)
    previous = locked.current_version
    if locked.status in {
        Message.Status.EFFECTIVE,
        Message.Status.EXPIRED,
        Message.Status.ARCHIVED,
        Message.Status.CANCELLED,
        Message.Status.WITHDRAWN,
    }:
        if title != previous.title or release_at != previous.release_at:
            raise ValidationError(
                "Title and release time cannot change after a message becomes effective."
            )
    replacement = MessageVersion(
        message=locked,
        version_number=locked.current_version_number + 1,
        title=title,
        summary=summary,
        text_content=text_content,
        searchable_content=text_content or previous.searchable_content,
        release_at=release_at,
        effective_at=effective_at,
        expiry_at=expiry_at,
        created_by=actor,
    )
    replacement.full_clean()
    replacement.save()
    rights = _validate_rights(actor=actor, message=locked, group_rights=group_rights)
    locked.audience_rights.all().delete()
    MessageAudienceRight.objects.bulk_create(rights)
    updated = Message.objects.filter(pk=locked.pk, lock_version=expected_version).update(
        current_version_number=replacement.version_number,
        lock_version=F("lock_version") + 1,
    )
    if updated != 1:
        raise StaleMessageError("Message was changed concurrently; refresh and retry.")
    locked.refresh_from_db()
    record_event(
        "message.revised",
        actor=actor,
        subject=locked,
        before={"version": previous.version_number},
        after={"version": replacement.version_number},
        reason=reason,
    )
    from firstbrief.notifications.services import schedule_message_lifecycle

    schedule_message_lifecycle(locked)
    return locked


def _transition(
    *,
    message: Message,
    actor: User | None,
    expected_version: int,
    idempotency_key: uuid.UUID,
    command: str,
    allowed_states: set[str],
    target_status: str,
    reason: str,
) -> Message:
    existing = LifecycleCommand.objects.filter(
        message=message, idempotency_key=idempotency_key
    ).first()
    if existing:
        if existing.command != command:
            raise ValidationError("Idempotency key was already used for another command.")
        message.refresh_from_db()
        return message
    locked = _lock_message(message, expected_version)
    if locked.status not in allowed_states:
        raise ValidationError(
            f"Cannot {command.replace('-', ' ')} a message in {locked.get_status_display()}."
        )
    from_status = locked.status
    updated = Message.objects.filter(pk=locked.pk, lock_version=expected_version).update(
        status=target_status, lock_version=F("lock_version") + 1
    )
    if updated != 1:
        raise StaleMessageError("Message was changed concurrently; refresh and retry.")
    locked.refresh_from_db()
    MessageStatusHistory.objects.create(
        message=locked,
        from_status=from_status,
        to_status=target_status,
        actor=actor,
        reason=reason,
        aggregate_version=locked.lock_version,
    )
    LifecycleCommand.objects.create(
        message=locked,
        idempotency_key=idempotency_key,
        command=command,
        resulting_status=target_status,
        aggregate_version=locked.lock_version,
    )
    record_event(
        f"message.{command}",
        actor=actor,
        subject=locked,
        before={"status": from_status, "lock_version": expected_version},
        after={"status": target_status, "lock_version": locked.lock_version},
        reason=reason,
    )
    return locked


@transaction.atomic
def approve_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    justification: str,
    validity_justification: str = "",
    idempotency_key: uuid.UUID,
    at: datetime | None = None,
) -> Message:
    require_capability(actor, APPROVE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "approved")
    if replayed is not None:
        return replayed
    if not justification.strip():
        raise ValidationError({"justification": "Approval justification is required."})
    locked = _lock_message(message, expected_version)
    if locked.status != Message.Status.DRAFT:
        raise ValidationError("Only Draft / Unapproved messages can be approved.")
    if (
        locked.approvers.exists()
        and not actor.is_superuser
        and not locked.approvers.filter(pk=actor.pk).exists()
    ):
        raise PermissionDenied("You are not an assigned approver for this message.")
    version = locked.current_version
    if locked.message_type.default_content_type == "pdf":
        roles = set(version.files.values_list("role", flat=True))
        if roles != {FileAsset.Role.DISPLAY, FileAsset.Role.PRINT}:
            raise ValidationError("Display and Print PDFs must pass validation before approval.")
    now = at or timezone.now()
    if version.release_at < now:
        version.release_at = now
        version.effective_at = max(version.effective_at, now) if version.effective_at else None
        version.full_clean()
        version.save(update_fields=("release_at", "effective_at"))
    if locked.subtype_id and version.effective_at:
        validity_days = (version.expiry_at - version.effective_at).total_seconds() / 86400
        subtype = locked.subtype
        if subtype is None:
            raise ValidationError({"subtype": "The configured subtype no longer exists."})
        minimum = subtype.minimum_validity_days
        maximum = subtype.maximum_validity_days
        outside = (minimum and validity_days < minimum) or (maximum and validity_days > maximum)
        if outside and not validity_justification.strip():
            raise ValidationError(
                {"validity_justification": "Justify validity outside subtype bounds."}
            )
    Approval.objects.create(
        message=locked,
        version=version,
        actor=actor,
        justification=justification,
        validity_justification=validity_justification,
    )
    approved = _transition(
        message=locked,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="approved",
        allowed_states={Message.Status.DRAFT},
        target_status=Message.Status.APPROVED_PENDING_RELEASE,
        reason=justification,
    )
    from firstbrief.notifications.services import register_message_approved

    register_message_approved(approved, at=now)
    return approved


@transaction.atomic
def release_message(
    *,
    actor: User | None,
    message: Message,
    expected_version: int,
    idempotency_key: uuid.UUID,
    at: datetime | None = None,
) -> Message:
    if actor is not None:
        require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "released")
    if replayed is not None:
        return replayed
    version = message.current_version
    now = at or timezone.now()
    if message.message_type.default_content_type == "pdf":
        roles = set(version.files.values_list("role", flat=True))
        if roles != {FileAsset.Role.DISPLAY, FileAsset.Role.PRINT}:
            raise ValidationError("Display and Print PDFs must pass validation before release.")
    if version.release_at > now:
        raise ValidationError("Message is not due for release.")
    target = (
        Message.Status.RELEASED_PENDING_EFFECTIVE
        if version.effective_at and version.effective_at > now
        else Message.Status.EFFECTIVE
    )
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="released",
        allowed_states={Message.Status.APPROVED_PENDING_RELEASE},
        target_status=target,
        reason="Release time reached.",
    )


@transaction.atomic
def make_effective(
    *,
    actor: User | None,
    message: Message,
    expected_version: int,
    idempotency_key: uuid.UUID,
    at: datetime | None = None,
) -> Message:
    if actor is not None:
        require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "effective")
    if replayed is not None:
        return replayed
    effective_at = message.current_version.effective_at
    if not effective_at or effective_at > (at or timezone.now()):
        raise ValidationError("Message is not due to become effective.")
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="effective",
        allowed_states={Message.Status.RELEASED_PENDING_EFFECTIVE},
        target_status=Message.Status.EFFECTIVE,
        reason="Effective time reached.",
    )


@transaction.atomic
def expire_message(
    *,
    actor: User | None,
    message: Message,
    expected_version: int,
    idempotency_key: uuid.UUID,
    at: datetime | None = None,
) -> Message:
    if actor is not None:
        require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "expired")
    if replayed is not None:
        return replayed
    if message.current_version.expiry_at > (at or timezone.now()):
        raise ValidationError("Message is not due to expire.")
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="expired",
        allowed_states={Message.Status.EFFECTIVE},
        target_status=Message.Status.EXPIRED,
        reason="Expiry time reached.",
    )


@transaction.atomic
def archive_message(
    *,
    actor: User | None,
    message: Message,
    expected_version: int,
    idempotency_key: uuid.UUID,
) -> Message:
    if actor is not None:
        require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "archived")
    if replayed is not None:
        return replayed
    if not message.archive_on_expiry and message.status == Message.Status.EXPIRED:
        raise ValidationError("Automatic archive is disabled for this message.")
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="archived",
        allowed_states={
            Message.Status.EXPIRED,
            Message.Status.CANCELLED,
            Message.Status.WITHDRAWN,
        },
        target_status=Message.Status.ARCHIVED,
        reason="Message archived.",
    )


@transaction.atomic
def withdraw_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    reason: str,
    idempotency_key: uuid.UUID,
) -> Message:
    require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "withdrawn")
    if replayed is not None:
        return replayed
    if not reason.strip():
        raise ValidationError({"reason": "Withdrawal reason is required."})
    effective_at = message.current_version.effective_at
    if effective_at and effective_at <= timezone.now():
        raise ValidationError("Effective messages must be cancelled, not withdrawn.")
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="withdrawn",
        allowed_states={
            Message.Status.APPROVED_PENDING_RELEASE,
            Message.Status.RELEASED_PENDING_EFFECTIVE,
        },
        target_status=Message.Status.WITHDRAWN,
        reason=reason,
    )


@transaction.atomic
def cancel_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    reason: str,
    idempotency_key: uuid.UUID,
) -> Message:
    require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "cancelled")
    if replayed is not None:
        return replayed
    if not reason.strip():
        raise ValidationError({"reason": "Cancellation reason is required."})
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="cancelled",
        allowed_states={
            Message.Status.RELEASED_PENDING_EFFECTIVE,
            Message.Status.EFFECTIVE,
        },
        target_status=Message.Status.CANCELLED,
        reason=reason,
    )


@transaction.atomic
def unapprove_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    reason: str,
    idempotency_key: uuid.UUID,
) -> Message:
    require_capability(actor, APPROVE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "unapproved")
    if replayed is not None:
        return replayed
    if not reason.strip():
        raise ValidationError({"reason": "Unapproval reason is required."})
    if message.current_version.release_at <= timezone.now():
        raise ValidationError("A message cannot be unapproved after its release time.")
    return _transition(
        message=message,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="unapproved",
        allowed_states={Message.Status.APPROVED_PENDING_RELEASE},
        target_status=Message.Status.DRAFT,
        reason=reason,
    )


@transaction.atomic
def restore_message(
    *,
    actor: User,
    message: Message,
    expected_version: int,
    future_expiry_at: datetime | None,
    reason: str,
    idempotency_key: uuid.UUID,
) -> Message:
    require_capability(actor, MANAGE_MESSAGES)
    replayed = _replayed_command(message, idempotency_key, "restored")
    if replayed is not None:
        return replayed
    if future_expiry_at is None:
        raise ValidationError({"future_expiry_at": "A new expiry time is required."})
    if future_expiry_at <= timezone.now():
        raise ValidationError({"future_expiry_at": "Restored expiry must be in the future."})
    locked = _lock_message(message, expected_version)
    version = locked.current_version
    replacement = MessageVersion(
        message=locked,
        version_number=locked.current_version_number + 1,
        title=version.title,
        summary=version.summary,
        text_content=version.text_content,
        searchable_content=version.searchable_content,
        release_at=version.release_at,
        effective_at=version.effective_at,
        expiry_at=future_expiry_at,
        created_by=actor,
    )
    replacement.full_clean()
    replacement.save()
    locked.current_version_number = replacement.version_number
    locked.save(update_fields=("current_version_number", "updated_at"))
    return _transition(
        message=locked,
        actor=actor,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        command="restored",
        allowed_states={Message.Status.ARCHIVED},
        target_status=Message.Status.EFFECTIVE,
        reason=reason or "Message restored.",
    )


@transaction.atomic
def supersede_message(
    *,
    actor: User,
    original: Message,
    replacement: Message,
    expected_original_version: int,
    reason: str,
) -> None:
    require_capability(actor, MANAGE_MESSAGES)
    locked = _lock_message(original, expected_original_version)
    if replacement.supersedes_id or Message.objects.filter(supersedes=locked).exists():
        raise ValidationError("A supersession link already exists.")
    replacement.supersedes = locked
    replacement.full_clean()
    replacement.save(update_fields=("supersedes", "updated_at"))
    Message.objects.filter(pk=locked.pk, lock_version=expected_original_version).update(
        lock_version=F("lock_version") + 1
    )
    record_event(
        "message.superseded",
        actor=actor,
        subject=locked,
        after={"replacement_id": replacement.message_id},
        reason=reason,
    )


def resolve_audience(message: Message, user: User) -> str | None:
    group_ids = user.message_groups.values_list("pk", flat=True)
    rights = set(
        message.audience_rights.filter(message_group_id__in=group_ids).values_list(
            "right", flat=True
        )
    )
    for right in (
        MessageAudienceRight.Right.PROHIBITED,
        MessageAudienceRight.Right.MANDATORY,
        MessageAudienceRight.Right.ALLOWED,
    ):
        if right in rights:
            return right
    return None


def require_message_access(message: Message, user: User) -> str:
    if user.is_superuser:
        return MessageAudienceRight.Right.ALLOWED
    right = resolve_audience(message, user)
    if right is None or right == MessageAudienceRight.Right.PROHIBITED:
        raise PermissionDenied("You do not have access to this message.")
    return right
