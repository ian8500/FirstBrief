"""Scoped operational queries and auditable message-consumption commands."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Exists, F, OuterRef, Q, QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    CREATE_MESSAGES,
    MANAGE_CONFIGURATION,
    MANAGE_MESSAGES,
    SEE_ALL_PMG,
    has_capability,
    require_capability,
)
from firstbrief.messaging.models import Message, MessageAudienceRight, MessageStatusHistory
from firstbrief.notifications.models import NotificationJob, NotificationPolicy
from firstbrief.notifications.services import apply_quiet_hours
from firstbrief.operations.models import (
    DashboardPreference,
    MessageAccessEvent,
    MessageReceipt,
    MessageViewSession,
    OperationalPolicy,
    ReadingPosition,
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


@dataclass(frozen=True)
class AttentionItem:
    key: str
    category: str
    urgency: str
    urgency_rank: int
    title: str
    reference: str
    reason: str
    due_at: datetime
    action_label: str
    action_url: str


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
    ).prefetch_related("audience_rights__message_group", "versions")
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
    preferences = DashboardPreference.load_for(user)
    all_messages = list(operational_messages(user))
    versions = {
        (version.message_id, version.version_number): version
        for message in all_messages
        for version in message.versions.all()
    }
    receipts = {
        receipt.message_id: receipt
        for receipt in MessageReceipt.objects.filter(
            user=user,
            message_id__in=[message.pk for message in all_messages],
        )
    }
    effective_since: list[Message] = []
    forthcoming: list[Message] = []
    botd: list[Message] = []
    attention: list[AttentionItem] = []
    included_messages: set[uuid.UUID] = set()

    def version_for(message: Message) -> Any:
        key = (message.pk, message.current_version_number)
        if key not in versions:
            versions[key] = next(
                version
                for version in message.versions.all()
                if version.version_number == message.current_version_number
            )
        return versions[key]

    def add_message_item(
        message: Message,
        *,
        category: str,
        urgency: str,
        rank: int,
        reason: str,
        due_at: datetime,
        management: bool = False,
        action_label: str = "Open message",
    ) -> None:
        if message.pk in included_messages:
            return
        included_messages.add(message.pk)
        version = version_for(message)
        attention.append(
            AttentionItem(
                key=f"{category}:{message.pk}",
                category=category,
                urgency=urgency,
                urgency_rank=rank,
                title=version.title,
                reference=message.message_id,
                reason=reason,
                due_at=due_at,
                action_label=action_label,
                action_url=reverse(
                    "messaging:detail" if management else "operations:viewer",
                    kwargs={"message_pk": message.pk},
                ),
            )
        )

    for message in all_messages:
        version = version_for(message)
        effective_at = version.effective_at or version.release_at
        mandatory = is_mandatory(message)
        receipt = receipts.get(message.pk)
        uncleared = not receipt or receipt.cleared_at is None
        unread = not receipt or receipt.first_read_at is None
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
        if mandatory and message.status == Message.Status.EFFECTIVE and uncleared:
            if effective_at >= previous_login_at:
                reason = (
                    "Became effective since your previous login and has not been "
                    "read and cleared."
                )
            elif receipt and receipt.first_read_at:
                reason = "Mandatory and effective; you opened it but have not cleared it."
            else:
                reason = "Mandatory and effective; it has not been read and cleared."
            add_message_item(
                message,
                category="overdue",
                urgency="Urgent",
                rank=0,
                reason=reason,
                due_at=effective_at,
                action_label=(
                    "Continue reading" if receipt and receipt.last_accessed_at else "Read now"
                ),
            )
        elif (
            preferences.show_forthcoming
            and message.status == Message.Status.RELEASED_PENDING_EFFECTIVE
        ):
            add_message_item(
                message,
                category="forthcoming",
                urgency="Forthcoming",
                rank=4,
                reason=f"Becomes effective within the next {policy.pre_effective_hours} hours.",
                due_at=effective_at,
                action_label="Preview message",
            )
        elif (
            preferences.show_botd
            and message.kind == Message.Kind.BOTD
            and message.status == Message.Status.EFFECTIVE
            and unread
            and message in botd
        ):
            add_message_item(
                message,
                category="botd",
                urgency="Unread",
                rank=3,
                reason="Current Brief of the Day for your default message group.",
                due_at=version.release_at,
                action_label="Read briefing",
            )

    management_scope = Message.objects.select_related(
        "message_type", "subtype", "originator"
    ).prefetch_related("versions")
    if not (user.is_superuser or has_capability(user, SEE_ALL_PMG)):
        if user.site_id:
            management_scope = management_scope.filter(
                audience_rights__message_group__primary_group__site_id=user.site_id
            ).distinct()
        else:
            management_scope = management_scope.none()

    returned_ids: set[uuid.UUID] = set()
    if preferences.show_returned_drafts and (
        has_capability(user, CREATE_MESSAGES) or has_capability(user, MANAGE_MESSAGES)
    ):
        returned = list(
            management_scope.filter(
                originator=user,
                status=Message.Status.DRAFT,
                status_history__from_status=Message.Status.APPROVED_PENDING_RELEASE,
                status_history__to_status=Message.Status.DRAFT,
            )
            .order_by("-updated_at", "message_id", "pk")
            .distinct()
        )
        returned_history: dict[uuid.UUID, MessageStatusHistory] = {}
        for history in MessageStatusHistory.objects.filter(
                message_id__in=[message.pk for message in returned],
                from_status=Message.Status.APPROVED_PENDING_RELEASE,
                to_status=Message.Status.DRAFT,
            ).order_by("message_id", "-occurred_at", "-pk"):
            returned_history.setdefault(history.message_id, history)
        for message in returned:
            returned_ids.add(message.pk)
            returned_event = returned_history.get(message.pk)
            add_message_item(
                message,
                category="returned",
                urgency="Action required",
                rank=1,
                reason=(
                    f"Returned for amendment: {returned_event.reason}"
                    if returned_event and returned_event.reason
                    else "Returned from approval for amendment."
                ),
                due_at=returned_event.occurred_at if returned_event else message.updated_at,
                management=True,
                action_label="Review draft",
            )

    if preferences.show_approvals and has_capability(user, APPROVE_MESSAGES):
        approvals = list(
            management_scope.filter(
                approvers=user,
                status=Message.Status.DRAFT,
            )
            .exclude(pk__in=returned_ids)
            .order_by("versions__release_at", "message_id", "pk")
            .distinct()
        )
        for message in approvals:
            version = version_for(message)
            add_message_item(
                message,
                category="approval",
                urgency="Approval required",
                rank=1,
                reason="You are an assigned approver and this draft is awaiting approval.",
                due_at=version.release_at,
                management=True,
                action_label="Review approval",
            )

    degraded_messages: list[str] = []
    can_manage = has_capability(user, MANAGE_MESSAGES)
    if preferences.show_notification_failures and can_manage:
        try:
            failed_jobs = list(
                NotificationJob.objects.filter(
                    status=NotificationJob.Status.DEAD,
                    message__in=management_scope,
                )
                .select_related("message")
                .order_by("next_attempt_at", "message__message_id", "pk")[:25]
            )
            for job in failed_jobs:
                attention.append(
                    AttentionItem(
                        key=f"notification:{job.pk}",
                        category="notification",
                        urgency="Delivery failed",
                        urgency_rank=0,
                        title=job.subject,
                        reference=job.message.message_id,
                        reason=(
                            "Notification delivery exhausted its retries and needs "
                            "administrator review."
                        ),
                        due_at=job.next_attempt_at,
                        action_label="Review delivery",
                        action_url=reverse("notifications:operations"),
                    )
                )
        except DatabaseError:
            degraded_messages.append(
                "Notification delivery status is temporarily unavailable. "
                "Message-reading tasks are unaffected."
            )

    if preferences.show_expiring_instructions and can_manage:
        expiry_cutoff = now + timedelta(days=preferences.expiring_within_days)
        expiring = list(
            management_scope.filter(
                kind=Message.Kind.INSTRUCTION,
                status=Message.Status.EFFECTIVE,
                versions__version_number=F("current_version_number"),
                versions__expiry_at__gt=now,
                versions__expiry_at__lte=expiry_cutoff,
            )
            .order_by("versions__expiry_at", "message_id", "pk")
            .distinct()
        )
        for message in expiring:
            version = version_for(message)
            add_message_item(
                message,
                category="expiring",
                urgency="Review soon",
                rank=2,
                reason=f"Instruction expires within {preferences.expiring_within_days} days.",
                due_at=version.expiry_at,
                management=True,
                action_label="Review instruction",
            )

    if preferences.show_recently_opened:
        recent_receipts = sorted(
            (
                receipt
                for receipt in receipts.values()
                if receipt.last_accessed_at and receipt.cleared_at is None
            ),
            key=lambda receipt: (receipt.last_accessed_at, str(receipt.message_id)),
            reverse=True,
        )
        messages_by_id = {message.pk: message for message in all_messages}
        for receipt in recent_receipts:
            recent_message = messages_by_id.get(receipt.message_id)
            if recent_message is None or receipt.last_accessed_at is None:
                continue
            add_message_item(
                recent_message,
                category="continue",
                urgency="In progress",
                rank=5,
                reason="You opened this message recently but did not clear it.",
                due_at=receipt.last_accessed_at,
                action_label="Continue reading",
            )

    attention.sort(
        key=lambda item: (
            item.urgency_rank,
            item.due_at,
            item.reference.casefold(),
            item.category,
            item.key,
        )
    )
    visible_attention = attention[: preferences.item_limit]
    continue_item = next(
        (item for item in attention if item.action_label == "Continue reading"),
        None,
    )
    return {
        "effective_since": sorted(
            effective_since,
            key=lambda message: (
                version_for(message).effective_at or version_for(message).release_at
            ),
            reverse=True,
        ),
        "forthcoming": sorted(
            forthcoming,
            key=lambda message: (
                version_for(message).effective_at or version_for(message).release_at
            ),
        ),
        "botd": sorted(botd, key=lambda message: version_for(message).release_at),
        "mandatory_unread": sum(
            1
            for message in all_messages
            if is_mandatory(message)
            and (
                message.pk not in receipts
                or receipts[message.pk].first_read_at is None
            )
            and (
                message.pk not in receipts
                or receipts[message.pk].cleared_at is None
            )
        ),
        "other_unread": sum(
            1
            for message in all_messages
            if (
                not is_mandatory(message)
                or (
                    message.pk in receipts
                    and receipts[message.pk].cleared_at is not None
                )
            )
            and (
                message.pk not in receipts
                or receipts[message.pk].first_read_at is None
            )
        ),
        "attention_items": visible_attention,
        "attention_total": len(attention),
        "attention_truncated": len(attention) > len(visible_attention),
        "continue_item": continue_item,
        "degraded_messages": degraded_messages,
        "preferences": preferences,
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
        version=message.current_version,
        mandatory_at_open=is_mandatory(message),
        browser_session_key=browser_session_key,
    )
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=MessageAccessEvent.EventType.OPENED,
        browser_session_key=browser_session_key,
        metadata={"version_number": message.current_version_number},
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
    lifecycle_changed: bool = False,
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
    version_number = (
        view_session.version.version_number
        if view_session.version_id and view_session.version is not None
        else message.current_version_number
    )
    if clear:
        MessageAccessEvent.objects.create(
            user=actor,
            message=message,
            event_type=MessageAccessEvent.EventType.ACKNOWLEDGED,
            browser_session_key=view_session.browser_session_key,
            duration_seconds=credited,
            metadata={"version_number": version_number},
        )
        record_event(
            "message.acknowledged",
            actor=actor,
            subject=message,
            after={"version_number": version_number, "viewing_seconds": credited},
        )
    event_type = (
        MessageAccessEvent.EventType.CLEARED
        if clear
        else MessageAccessEvent.EventType.READ
    )
    MessageAccessEvent.objects.create(
        user=actor,
        message=message,
        event_type=event_type,
        browser_session_key=view_session.browser_session_key,
        duration_seconds=credited,
        metadata={
            "version_number": version_number,
            "lifecycle_changed_while_open": lifecycle_changed,
        },
    )
    record_event(
        f"message.{event_type}",
        actor=actor,
        subject=message,
        after={
            "viewing_seconds": credited,
            "acknowledged": clear,
            "version_number": version_number,
            "lifecycle_changed_while_open": lifecycle_changed,
        },
    )
    return receipt


@transaction.atomic
def save_reading_position(
    *,
    actor: User,
    message: Message,
    view_session_id: uuid.UUID,
    page: int,
    total_pages: int,
) -> ReadingPosition:
    try:
        view_session = MessageViewSession.objects.select_related("version").get(
            pk=view_session_id,
            user=actor,
            message=message,
            closed_at__isnull=True,
        )
    except MessageViewSession.DoesNotExist as exc:
        raise PermissionDenied("This viewing session is not available.") from exc
    if view_session.version_id is None:
        raise ValidationError("This viewing session does not identify a message version.")
    total_pages = min(max(total_pages, 1), 5000)
    page = min(max(page, 1), total_pages)
    position, _ = ReadingPosition.objects.update_or_create(
        user=actor,
        message=message,
        version_id=view_session.version_id,
        defaults={"page": page, "total_pages": total_pages},
    )
    return position


def active_session_message(
    *,
    actor: User,
    message_pk: uuid.UUID,
    view_session_id: uuid.UUID,
) -> tuple[Message, MessageViewSession]:
    try:
        session = MessageViewSession.objects.select_related(
            "message",
            "message__message_type",
            "message__subtype",
            "message__originator",
            "version",
        ).get(
            pk=view_session_id,
            user=actor,
            message_id=message_pk,
            closed_at__isnull=True,
        )
    except MessageViewSession.DoesNotExist as exc:
        raise PermissionDenied("This viewing session is not available.") from exc
    return session.message, session


def adjacent_mandatory_messages(
    user: User,
    message: Message,
) -> tuple[Message | None, Message | None]:
    rows = message_rows(user, list_kind="mandatory", sort="effective")
    ids = [row.message.pk for row in rows]
    if message.pk not in ids:
        return None, None
    index = ids.index(message.pk)
    previous = rows[index - 1].message if index > 0 else None
    following = rows[index + 1].message if index + 1 < len(rows) else None
    return previous, following


def related_messages(user: User, message: Message) -> list[Message]:
    queryset = operational_messages(user).exclude(pk=message.pk)
    if message.subtype_id:
        queryset = queryset.filter(subtype_id=message.subtype_id)
    else:
        queryset = queryset.filter(message_type_id=message.message_type_id)
    return list(queryset.order_by("-updated_at", "message_id", "pk")[:5])


def version_change_summary(message: Message) -> list[str]:
    if message.current_version_number <= 1:
        return []
    versions = {
        version.version_number: version
        for version in message.versions.filter(
            version_number__in=(message.current_version_number - 1, message.current_version_number)
        ).prefetch_related("files")
    }
    current = versions.get(message.current_version_number)
    previous = versions.get(message.current_version_number - 1)
    if current is None or previous is None:
        return []
    changes: list[str] = []
    for field, label in (
        ("title", "Title"),
        ("summary", "Summary"),
        ("text_content", "Text content"),
        ("release_at", "Release time"),
        ("effective_at", "Effective time"),
        ("expiry_at", "Expiry time"),
    ):
        if getattr(current, field) != getattr(previous, field):
            changes.append(f"{label} changed.")
    if current.files.count() != previous.files.count():
        changes.append("Protected PDF attachments changed.")
    return changes


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
