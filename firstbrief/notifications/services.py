"""Transactional scheduling, outbox processing and retry-safe email delivery."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import IdentityPolicy, User
from firstbrief.identity.services import MANAGE_MESSAGES, require_capability
from firstbrief.messaging.models import Message
from firstbrief.messaging.services import (
    archive_message,
    expire_message,
    make_effective,
    release_message,
)
from firstbrief.notifications.models import (
    LifecycleJob,
    NotificationJob,
    NotificationPolicy,
    OutboxEvent,
)

MESSAGE_CREATED = "message-created"
MESSAGE_APPROVED = "message-approved"
UNAPPROVED_EFFECTIVE = "unapproved-effective"


def _deduplicated_recipients(values: list[str]) -> list[str]:
    return sorted({value.strip().casefold() for value in values if value.strip()})


def _creation_recipients(message: Message) -> list[str]:
    approvers = list(message.approvers.exclude(email="").values_list("email", flat=True))
    distributions: list[str] = []
    subtype = message.subtype
    if subtype is not None:
        distributions = list(
            subtype.email_distributions.filter(use_as_email=True).values_list(
                "email_address", flat=True
            )
        )
    return _deduplicated_recipients(approvers + distributions)


def _approval_recipients(message: Message) -> list[str]:
    policy = IdentityPolicy.load()
    recipients = [policy.approval_notification_email]
    subtype = message.subtype
    if subtype is not None:
        recipients.extend(
            subtype.email_distributions.filter(use_as_email=True).values_list(
                "email_address", flat=True
            )
        )
    return _deduplicated_recipients(recipients)


def _unapproved_recipients() -> list[str]:
    return _deduplicated_recipients([IdentityPolicy.load().policy_notification_email])


def _anchor_time(message: Message, anchor: str, event_time: datetime) -> datetime:
    version = message.current_version
    if anchor == NotificationPolicy.Anchor.RELEASE:
        return version.release_at
    if anchor == NotificationPolicy.Anchor.EFFECTIVE:
        return version.effective_at or version.release_at
    return event_time


def apply_quiet_hours(value: datetime, policy: NotificationPolicy) -> datetime:
    if not policy.quiet_hours_start or not policy.quiet_hours_end:
        return value
    try:
        zone = ZoneInfo(policy.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError({"timezone_name": "Unknown IANA timezone."}) from exc
    local = value.astimezone(zone)
    start = policy.quiet_hours_start
    end = policy.quiet_hours_end
    local_time = local.timetz().replace(tzinfo=None)
    if start < end:
        in_quiet = start <= local_time < end
        end_date = local.date()
    else:
        in_quiet = local_time >= start or local_time < end
        end_date = local.date() + timedelta(days=1) if local_time >= start else local.date()
    if not in_quiet:
        return value
    quiet_end = datetime.combine(end_date, end, tzinfo=zone)
    return quiet_end.astimezone(UTC)


def _notification_time(
    message: Message, *, event_time: datetime, anchor: str, offset_minutes: int
) -> datetime:
    policy = NotificationPolicy.load()
    scheduled = _anchor_time(message, anchor, event_time) + timedelta(minutes=offset_minutes)
    return apply_quiet_hours(scheduled, policy)


def _enqueue_outbox(
    *,
    topic: str,
    message: Message,
    recipients: list[str],
    available_at: datetime,
    event_key: str,
) -> OutboxEvent:
    event, _ = OutboxEvent.objects.get_or_create(
        deduplication_key=event_key,
        defaults={
            "topic": topic,
            "payload": {
                "message_pk": str(message.pk),
                "message_id": message.message_id,
                "version_number": message.current_version_number,
                "recipients": recipients,
            },
            "available_at": available_at,
        },
    )
    return event


@transaction.atomic
def schedule_message_lifecycle(message: Message) -> list[LifecycleJob]:
    version = message.current_version
    policy = NotificationPolicy.load()
    LifecycleJob.objects.filter(message=message, status=LifecycleJob.Status.PENDING).exclude(
        version_number=version.version_number
    ).update(status=LifecycleJob.Status.CANCELLED)
    specifications: list[tuple[str, datetime | None]] = [
        (LifecycleJob.Transition.RELEASE, version.release_at),
        (LifecycleJob.Transition.EFFECTIVE, version.effective_at),
        (LifecycleJob.Transition.EXPIRE, version.expiry_at),
        (
            LifecycleJob.Transition.ARCHIVE,
            version.expiry_at if message.archive_on_expiry else None,
        ),
        (
            LifecycleJob.Transition.RETENTION_REVIEW,
            version.expiry_at + timedelta(days=policy.archive_retention_days),
        ),
        (LifecycleJob.Transition.UNAPPROVED_ALERT, version.effective_at),
    ]
    jobs: list[LifecycleJob] = []
    for transition, due_at in specifications:
        if due_at is None:
            continue
        key = f"lifecycle:{message.pk}:{version.version_number}:{transition}"
        job, _ = LifecycleJob.objects.update_or_create(
            deduplication_key=key,
            defaults={
                "message": message,
                "version_number": version.version_number,
                "transition": transition,
                "due_at": due_at,
                "status": LifecycleJob.Status.PENDING,
                "attempts": 0,
                "last_error": "",
                "completed_at": None,
            },
        )
        jobs.append(job)
    return jobs


@transaction.atomic
def register_message_created(message: Message, *, at: datetime | None = None) -> None:
    event_time = at or timezone.now()
    schedule_message_lifecycle(message)
    policy = NotificationPolicy.load()
    available_at = _notification_time(
        message,
        event_time=event_time,
        anchor=policy.creation_anchor,
        offset_minutes=policy.creation_offset_minutes,
    )
    _enqueue_outbox(
        topic=MESSAGE_CREATED,
        message=message,
        recipients=_creation_recipients(message),
        available_at=available_at,
        event_key=f"message-created:{message.pk}:{message.current_version_number}",
    )


@transaction.atomic
def register_message_approved(message: Message, *, at: datetime | None = None) -> None:
    event_time = at or timezone.now()
    schedule_message_lifecycle(message)
    policy = NotificationPolicy.load()
    available_at = _notification_time(
        message,
        event_time=event_time,
        anchor=policy.approval_anchor,
        offset_minutes=policy.approval_offset_minutes,
    )
    _enqueue_outbox(
        topic=MESSAGE_APPROVED,
        message=message,
        recipients=_approval_recipients(message),
        available_at=available_at,
        event_key=f"message-approved:{message.pk}:{message.current_version_number}",
    )


def _notification_copy(topic: str, message: Message) -> tuple[str, str, str]:
    template_names = {
        MESSAGE_CREATED: ("created", NotificationJob.Kind.CREATED),
        MESSAGE_APPROVED: ("approved", NotificationJob.Kind.APPROVED),
        UNAPPROVED_EFFECTIVE: (
            "unapproved_effective",
            NotificationJob.Kind.UNAPPROVED_EFFECTIVE,
        ),
    }
    template_name, kind = template_names[topic]
    context = {"message": message, "version": message.current_version}
    subject = " ".join(
        render_to_string(f"notifications/email/{template_name}_subject.txt", context).splitlines()
    ).strip()
    body = render_to_string(f"notifications/email/{template_name}_body.txt", context).strip()
    return kind, subject, body


@transaction.atomic
def process_outbox(*, now: datetime | None = None, limit: int = 100) -> int:
    current = now or timezone.now()
    events = list(
        OutboxEvent.objects.select_for_update(skip_locked=True)
        .filter(status=OutboxEvent.Status.PENDING, available_at__lte=current)
        .order_by("available_at", "pk")[:limit]
    )
    processed = 0
    policy = NotificationPolicy.load()
    for event in events:
        event.status = OutboxEvent.Status.PROCESSING
        event.attempts += 1
        event.save(update_fields=("status", "attempts"))
        try:
            message = Message.objects.get(pk=event.payload["message_pk"])
            recipients = _deduplicated_recipients(event.payload.get("recipients", []))
            if recipients:
                kind, subject, body = _notification_copy(event.topic, message)
                NotificationJob.objects.get_or_create(
                    deduplication_key=f"notification:{event.deduplication_key}",
                    defaults={
                        "message": message,
                        "kind": kind,
                        "recipients": recipients,
                        "subject": subject,
                        "body": body,
                        "scheduled_at": event.available_at,
                        "next_attempt_at": current,
                    },
                )
            event.status = OutboxEvent.Status.PUBLISHED
            event.processed_at = current
            event.last_error = ""
            event.save(update_fields=("status", "processed_at", "last_error"))
            processed += 1
        except Exception as exc:
            event.last_error = f"{exc.__class__.__name__}: {exc}"[:1000]
            event.status = (
                OutboxEvent.Status.DEAD
                if event.attempts >= policy.maximum_attempts
                else OutboxEvent.Status.PENDING
            )
            event.available_at = current + timedelta(
                minutes=policy.retry_delay_minutes * (2 ** (event.attempts - 1))
            )
            event.save(update_fields=("status", "last_error", "available_at"))
    return processed


def _lifecycle_idempotency_key(job: LifecycleJob) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, job.deduplication_key)


@transaction.atomic
def process_due_lifecycle(*, now: datetime | None = None, limit: int = 100) -> int:
    current = now or timezone.now()
    jobs = list(
        LifecycleJob.objects.select_for_update(skip_locked=True)
        .select_related("message")
        .filter(status=LifecycleJob.Status.PENDING, due_at__lte=current)
        .order_by("due_at", "pk")[:limit]
    )
    completed = 0
    policy = NotificationPolicy.load()
    for job in jobs:
        message = job.message
        message.refresh_from_db()
        job.attempts += 1
        try:
            if job.version_number != message.current_version_number:
                job.status = LifecycleJob.Status.CANCELLED
            elif job.transition == LifecycleJob.Transition.RELEASE:
                if message.status == Message.Status.APPROVED_PENDING_RELEASE:
                    release_message(
                        actor=None,
                        message=message,
                        expected_version=message.lock_version,
                        idempotency_key=_lifecycle_idempotency_key(job),
                        at=current,
                    )
                    job.status = LifecycleJob.Status.COMPLETED
                else:
                    job.status = LifecycleJob.Status.SKIPPED
            elif job.transition == LifecycleJob.Transition.EFFECTIVE:
                if message.status == Message.Status.RELEASED_PENDING_EFFECTIVE:
                    make_effective(
                        actor=None,
                        message=message,
                        expected_version=message.lock_version,
                        idempotency_key=_lifecycle_idempotency_key(job),
                        at=current,
                    )
                    job.status = LifecycleJob.Status.COMPLETED
                else:
                    job.status = LifecycleJob.Status.SKIPPED
            elif job.transition == LifecycleJob.Transition.EXPIRE:
                if message.status == Message.Status.EFFECTIVE:
                    expire_message(
                        actor=None,
                        message=message,
                        expected_version=message.lock_version,
                        idempotency_key=_lifecycle_idempotency_key(job),
                        at=current,
                    )
                    job.status = LifecycleJob.Status.COMPLETED
                else:
                    job.status = LifecycleJob.Status.SKIPPED
            elif job.transition == LifecycleJob.Transition.ARCHIVE:
                if message.status == Message.Status.EXPIRED and message.archive_on_expiry:
                    archive_message(
                        actor=None,
                        message=message,
                        expected_version=message.lock_version,
                        idempotency_key=_lifecycle_idempotency_key(job),
                    )
                    job.status = LifecycleJob.Status.COMPLETED
                else:
                    job.status = LifecycleJob.Status.SKIPPED
            elif job.transition == LifecycleJob.Transition.RETENTION_REVIEW:
                if message.status == Message.Status.ARCHIVED:
                    record_event(
                        "message.retention_review_due",
                        subject=message,
                        after={"retention_job": job.pk},
                    )
                    job.status = LifecycleJob.Status.COMPLETED
                else:
                    job.status = LifecycleJob.Status.SKIPPED
            elif (
                job.transition == LifecycleJob.Transition.UNAPPROVED_ALERT
                and message.status == Message.Status.DRAFT
            ):
                _enqueue_outbox(
                    topic=UNAPPROVED_EFFECTIVE,
                    message=message,
                    recipients=_unapproved_recipients(),
                    available_at=current,
                    event_key=(
                        f"unapproved-effective:{message.pk}:{message.current_version_number}"
                    ),
                )
                job.status = LifecycleJob.Status.COMPLETED
            else:
                job.status = LifecycleJob.Status.SKIPPED
            job.completed_at = current
            job.last_error = ""
            completed += 1
        except Exception as exc:
            job.last_error = f"{exc.__class__.__name__}: {exc}"[:1000]
            job.status = (
                LifecycleJob.Status.DEAD
                if job.attempts >= policy.maximum_attempts
                else LifecycleJob.Status.PENDING
            )
            job.due_at = current + timedelta(
                minutes=policy.retry_delay_minutes * (2 ** (job.attempts - 1))
            )
        job.save(
            update_fields=(
                "status",
                "attempts",
                "last_error",
                "completed_at",
                "due_at",
            )
        )
    return completed


@transaction.atomic
def deliver_notifications(*, now: datetime | None = None, limit: int = 100) -> int:
    current = now or timezone.now()
    jobs = list(
        NotificationJob.objects.select_for_update(skip_locked=True)
        .filter(status=NotificationJob.Status.PENDING, next_attempt_at__lte=current)
        .order_by("next_attempt_at", "pk")[:limit]
    )
    sent = 0
    policy = NotificationPolicy.load()
    for job in jobs:
        allowed_at = apply_quiet_hours(current, policy)
        if allowed_at > current:
            job.next_attempt_at = allowed_at
            job.save(update_fields=("next_attempt_at",))
            continue
        job.attempts += 1
        try:
            send_mail(
                job.subject,
                job.body,
                settings.DEFAULT_FROM_EMAIL,
                job.recipients,
                fail_silently=False,
            )
            job.status = NotificationJob.Status.SENT
            job.sent_at = current
            job.last_error = ""
            sent += 1
            record_event("notification.sent", subject=job.message, after={"job": job.pk})
        except Exception as exc:
            job.last_error = f"{exc.__class__.__name__}: {exc}"[:1000]
            job.status = (
                NotificationJob.Status.DEAD
                if job.attempts >= policy.maximum_attempts
                else NotificationJob.Status.PENDING
            )
            job.next_attempt_at = current + timedelta(
                minutes=policy.retry_delay_minutes * (2 ** (job.attempts - 1))
            )
        job.save(
            update_fields=(
                "status",
                "attempts",
                "last_error",
                "next_attempt_at",
                "sent_at",
            )
        )
    return sent


@transaction.atomic
def manual_resend(
    *, actor: User, job: NotificationJob, now: datetime | None = None
) -> NotificationJob:
    require_capability(actor, MANAGE_MESSAGES)
    current = now or timezone.now()
    resent = NotificationJob.objects.create(
        message=job.message,
        kind=NotificationJob.Kind.MANUAL_RESEND,
        recipients=job.recipients,
        subject=job.subject,
        body=job.body,
        deduplication_key=f"manual-resend:{job.pk}:{uuid.uuid4()}",
        scheduled_at=current,
        next_attempt_at=current,
    )
    record_event(
        "notification.manual_resend",
        actor=actor,
        subject=job.message,
        after={"source_job": job.pk, "new_job": resent.pk},
    )
    return resent
