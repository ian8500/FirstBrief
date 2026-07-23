"""Celery entry points for recoverable database-backed orchestration."""

from celery import shared_task

from firstbrief.notifications.services import (
    deliver_notifications,
    process_due_lifecycle,
    process_outbox,
)


@shared_task(name="firstbrief.notifications.process_outbox")  # type: ignore[untyped-decorator]
def process_outbox_task() -> int:
    return process_outbox()


@shared_task(name="firstbrief.notifications.process_lifecycle")  # type: ignore[untyped-decorator]
def process_lifecycle_task() -> int:
    return process_due_lifecycle()


@shared_task(name="firstbrief.notifications.deliver")  # type: ignore[untyped-decorator]
def deliver_notifications_task() -> int:
    return deliver_notifications()
