"""Foundation persistence models."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models

SENSITIVE_KEY_FRAGMENTS = {"password", "secret", "token", "credential", "private_key"}


class SystemSetting(models.Model):
    """Non-secret runtime configuration.

    Secrets belong in the deployment secrets manager and are rejected here by key.
    """

    key = models.SlugField(max_length=128, unique=True)
    value = models.JSONField()
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)

    def __str__(self) -> str:
        return self.key

    def clean(self) -> None:
        super().clean()
        lowered = self.key.lower()
        if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
            raise ValidationError(
                {"key": "Secrets and credentials must use the deployment secrets manager."}
            )
