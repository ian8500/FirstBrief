"""Report reference data, import evidence and immutable run snapshots."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ReportingCohort(models.Model):
    class Kind(models.TextChoices):
        USER_GROUP = "user_group", "User group"
        WATCH_GROUP = "watch_group", "Watch group"

    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    site = models.ForeignKey(
        "configuration.Site", on_delete=models.PROTECT, related_name="reporting_cohorts"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="reporting_cohorts"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", "pk")

    def __str__(self) -> str:
        return f"{self.name} ({self.get_kind_display()})"


class ImportChangeRecord(models.Model):
    """Stable reporting contract for Prompt 9 import commits."""

    batch_reference = models.CharField(max_length=100, db_index=True)
    site = models.ForeignKey(
        "configuration.Site", on_delete=models.PROTECT, related_name="import_change_records"
    )
    change_type = models.CharField(max_length=40)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    summary = models.CharField(max_length=500)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("occurred_at", "pk")

    def __str__(self) -> str:
        return f"{self.batch_reference}: {self.change_type} {self.object_type}"


class AppendOnlyReportRunQuerySet(models.QuerySet["ReportRun"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Report runs are retained evidence.")


class ReportRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="report_runs"
    )
    report_code = models.CharField(max_length=8, db_index=True)
    catalogue_version = models.PositiveSmallIntegerField(default=1)
    criteria = models.JSONField(default=dict)
    columns = models.JSONField(default=list)
    rows = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    row_count = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = AppendOnlyReportRunQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at", "-pk")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("actor", "status", "created_at"), name="report_actor_status_time")
        ]

    def __str__(self) -> str:
        return f"{self.report_code} by {self.actor} ({self.status})"

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Report runs are retained evidence.")
