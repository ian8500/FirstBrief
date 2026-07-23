"""Append-only security and business audit events."""

from __future__ import annotations

from typing import Any

from django.conf import settings
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
