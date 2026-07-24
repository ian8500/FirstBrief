"""Append-only security and business audit events."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class AppendOnlyQuerySet(models.QuerySet["AuditEvent"]):
    def update(self, **kwargs: Any) -> int:
        raise TypeError("Audit events are append-only")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise TypeError("Audit events are append-only")


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    correlation_id = models.CharField(max_length=128, blank=True)
    reason = models.TextField(blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ("-occurred_at", "-pk")

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            raise TypeError("Audit events are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise TypeError("Audit events are append-only")


class RetentionPolicy(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    archived_months = models.PositiveSmallIntegerField(
        default=84, validators=[MinValueValidator(1)]
    )
    expired_months = models.PositiveSmallIntegerField(default=84, validators=[MinValueValidator(1)])
    require_second_approver = models.BooleanField(default=True)

    def __str__(self) -> str:
        return "Retention policy"

    @classmethod
    def load(cls) -> RetentionPolicy:
        policy, _ = cls.objects.get_or_create(singleton=True)
        return policy


class LegalHold(models.Model):
    name = models.CharField(max_length=160)
    reason = models.TextField()
    message = models.ForeignKey(
        "messaging.Message", on_delete=models.PROTECT, related_name="legal_holds"
    )
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_legal_holds"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class PurgeRun(models.Model):
    class Status(models.TextChoices):
        PREVIEW = "preview", "Preview"
        APPROVED = "approved", "Approved"
        COMPLETE = "complete", "Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREVIEW)
    candidates = models.JSONField(default=list)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_purges"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved_purges",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence_sha256 = models.CharField(max_length=64, blank=True)

    def __str__(self) -> str:
        return f"Purge {self.pk} ({self.get_status_display()})"
