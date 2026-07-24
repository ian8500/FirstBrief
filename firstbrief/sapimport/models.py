"""Immutable staged imports and their reviewed change set."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        STAGED = "staged", "Ready for review"
        REJECTED = "rejected", "File in error"
        COMMITTED = "committed", "Process complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    content_sha256 = models.CharField(max_length=64)
    staged_content = models.TextField()
    schema_version = models.CharField(max_length=16, default="1")
    status = models.CharField(max_length=16, choices=Status.choices)
    error = models.TextField(blank=True)
    staged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="staged_imports"
    )
    staged_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-staged_at",)

    def __str__(self) -> str:
        return f"{self.filename} ({self.get_status_display()})"

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("Import evidence is retained.")


class ImportChange(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="changes")
    row_number = models.PositiveIntegerField()
    site_code = models.SlugField(max_length=64)
    action = models.CharField(max_length=16)
    user_id = models.CharField(max_length=150)
    payload = models.JSONField(default=dict)
    selected = models.BooleanField(default=True)
    applied = models.BooleanField(default=False)
    outcome = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("site_code", "row_number")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("batch", "row_number"), name="unique_import_batch_row")
        ]

    def __str__(self) -> str:
        return f"{self.batch.filename} row {self.row_number}: {self.user_id}"
