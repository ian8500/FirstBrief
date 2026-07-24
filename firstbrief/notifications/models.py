"""Authoritative outbox, lifecycle schedule and notification delivery records."""

from __future__ import annotations

from typing import ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class NotificationPolicy(models.Model):
    class Anchor(models.TextChoices):
        NOW = "now", "Event time"
        RELEASE = "release", "Release time"
        EFFECTIVE = "effective", "Effective time"

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    creation_anchor = models.CharField(max_length=12, choices=Anchor.choices, default=Anchor.NOW)
    creation_offset_minutes = models.IntegerField(default=0)
    approval_anchor = models.CharField(max_length=12, choices=Anchor.choices, default=Anchor.NOW)
    approval_offset_minutes = models.IntegerField(default=0)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    timezone_name = models.CharField(max_length=64, default="Europe/London")
    maximum_attempts = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1)]
    )
    retry_delay_minutes = models.PositiveIntegerField(default=5, validators=[MinValueValidator(1)])
    archive_retention_days = models.PositiveIntegerField(
        default=365, validators=[MinValueValidator(1)]
    )

    def __str__(self) -> str:
        return "Notification delivery policy"

    def clean(self) -> None:
        super().clean()
        if bool(self.quiet_hours_start) != bool(self.quiet_hours_end):
            raise ValidationError(
                "Quiet-hours start and end must either both be set or both be blank."
            )
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(self.timezone_name)
        except Exception as exc:
            raise ValidationError({"timezone_name": "Enter a valid IANA timezone."}) from exc

    @classmethod
    def load(cls) -> NotificationPolicy:
        policy, _ = cls.objects.get_or_create(singleton=True)
        return policy


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PUBLISHED = "published", "Published"
        DEAD = "dead", "Dead letter"

    topic = models.SlugField(max_length=80)
    payload = models.JSONField(default=dict)
    deduplication_key = models.CharField(max_length=180, unique=True)
    available_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("available_at", "pk")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("status", "available_at"), name="outbox_due"),
        ]

    def __str__(self) -> str:
        return f"{self.topic}: {self.deduplication_key}"


class LifecycleJob(models.Model):
    class Transition(models.TextChoices):
        RELEASE = "release", "Release"
        EFFECTIVE = "effective", "Become effective"
        EXPIRE = "expire", "Expire"
        ARCHIVE = "archive", "Archive"
        RETENTION_REVIEW = "retention_review", "Retention review"
        UNAPPROVED_ALERT = "unapproved_alert", "Unapproved-at-effective alert"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"
        DEAD = "dead", "Dead letter"
        CANCELLED = "cancelled", "Cancelled"

    message = models.ForeignKey(
        "messaging.Message", on_delete=models.PROTECT, related_name="lifecycle_jobs"
    )
    version_number = models.PositiveIntegerField()
    transition = models.CharField(max_length=24, choices=Transition.choices)
    due_at = models.DateTimeField()
    deduplication_key = models.CharField(max_length=180, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("due_at", "pk")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("status", "due_at"), name="lifecycle_due"),
        ]

    def __str__(self) -> str:
        return f"{self.message.message_id}: {self.get_transition_display()}"


class NotificationJob(models.Model):
    class Kind(models.TextChoices):
        CREATED = "created", "Message created"
        APPROVED = "approved", "Message approved"
        UNAPPROVED_EFFECTIVE = "unapproved_effective", "Unapproved at effective time"
        MANUAL_RESEND = "manual_resend", "Manual resend"
        MESSAGE_TO_SELF = "message_to_self", "Message emailed to user"
        FEEDBACK = "feedback", "Message feedback"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DEAD = "dead", "Dead letter"
        CANCELLED = "cancelled", "Cancelled"

    message = models.ForeignKey(
        "messaging.Message", on_delete=models.PROTECT, related_name="notification_jobs"
    )
    kind = models.CharField(max_length=24, choices=Kind.choices)
    recipients = models.JSONField(default=list)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    deduplication_key = models.CharField(max_length=180, unique=True)
    scheduled_at = models.DateTimeField()
    next_attempt_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("next_attempt_at", "pk")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("status", "next_attempt_at"), name="notification_due"),
        ]

    def __str__(self) -> str:
        return f"{self.message.message_id}: {self.get_kind_display()}"
