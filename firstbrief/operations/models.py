"""Operational reading, acknowledgement and access evidence."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


class OperationalPolicy(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    pre_effective_hours = models.PositiveSmallIntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(720)],
        help_text="Hours before effective time that forthcoming messages appear.",
    )
    pre_effective_colour = models.CharField(
        max_length=7,
        default="#6f42c1",
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="Enter a six-digit hexadecimal colour such as #6f42c1.",
            )
        ],
        help_text="A text label and icon are also shown; colour is never the only cue.",
    )
    idle_timeout_seconds = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(15), MaxValueValidator(900)],
        help_text="Viewing time pauses after this many seconds without activity.",
    )

    def __str__(self) -> str:
        return "Operational dashboard policy"

    @classmethod
    def load(cls) -> OperationalPolicy:
        policy, _ = cls.objects.get_or_create(singleton=True)
        return policy


class DashboardPreference(models.Model):
    class ItemLimit(models.IntegerChoices):
        FIVE = 5, "5 items"
        TEN = 10, "10 items"
        TWENTY = 20, "20 items"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_preference",
    )
    show_forthcoming = models.BooleanField(default=True)
    show_botd = models.BooleanField(default=True)
    show_approvals = models.BooleanField(default=True)
    show_returned_drafts = models.BooleanField(default=True)
    show_notification_failures = models.BooleanField(default=True)
    show_expiring_instructions = models.BooleanField(default=True)
    show_recently_opened = models.BooleanField(default=True)
    item_limit = models.PositiveSmallIntegerField(
        choices=ItemLimit.choices,
        default=ItemLimit.TEN,
    )
    expiring_within_days = models.PositiveSmallIntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Show authorised instructions expiring within this many days.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Dashboard preferences for {self.user}"

    @classmethod
    def load_for(cls, user: Any) -> DashboardPreference:
        preference, _ = cls.objects.get_or_create(user=user)
        return preference


class MessageReceipt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="message_receipts",
    )
    message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.PROTECT,
        related_name="receipts",
    )
    first_read_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)
    cumulative_view_seconds = models.PositiveIntegerField(default=0)
    printed_at = models.DateTimeField(null=True, blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("user", "message"),
                name="unique_user_message_receipt",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("user", "cleared_at"), name="receipt_user_cleared"),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.message}"


class MessageViewSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="message_view_sessions",
    )
    message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.PROTECT,
        related_name="view_sessions",
    )
    version = models.ForeignKey(
        "messaging.MessageVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="view_sessions",
    )
    mandatory_at_open = models.BooleanField(default=False)
    browser_session_key = models.CharField(max_length=40, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    active_seconds = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.user}: {self.message} at {self.opened_at}"


class ReadingPosition(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_positions",
    )
    message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.CASCADE,
        related_name="reading_positions",
    )
    version = models.ForeignKey(
        "messaging.MessageVersion",
        on_delete=models.CASCADE,
        related_name="reading_positions",
    )
    page = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    total_pages = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("user", "message", "version"),
                name="unique_user_message_version_position",
            ),
            models.CheckConstraint(
                condition=models.Q(page__lte=models.F("total_pages")),
                name="reading_page_within_total",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("user", "message", "version"),
                name="reading_position_lookup",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.message} v{self.version.version_number} p{self.page}"


class AppendOnlyAccessEventQuerySet(models.QuerySet["MessageAccessEvent"]):
    def update(self, **kwargs: Any) -> int:
        raise ValidationError("Message access events are append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Message access events are append-only.")


class MessageAccessEvent(models.Model):
    class EventType(models.TextChoices):
        OPENED = "opened", "Opened"
        READ = "read", "Read"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        CLEARED = "cleared", "Read and cleared"
        PRINTED = "printed", "Printed"
        EMAILED = "emailed", "Emailed to self"
        FEEDBACK = "feedback", "Feedback sent"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="message_access_events",
    )
    message = models.ForeignKey(
        "messaging.Message",
        on_delete=models.PROTECT,
        related_name="access_events",
    )
    event_type = models.CharField(max_length=16, choices=EventType.choices)
    browser_session_key = models.CharField(max_length=40, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyAccessEventQuerySet.as_manager()

    class Meta:
        ordering = ("occurred_at", "pk")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("user", "message", "occurred_at"),
                name="access_user_message_time",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.message} {self.get_event_type_display()}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise ValidationError("Message access events are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Message access events are append-only.")
