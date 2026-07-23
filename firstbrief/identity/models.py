"""Identity and access-control persistence."""

from __future__ import annotations

from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Capability(models.Model):
    codename = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=160)

    class Meta:
        ordering = ("codename",)

    def __str__(self) -> str:
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    capabilities = models.ManyToManyField(Capability, blank=True, related_name="roles")
    message_types = models.ManyToManyField(
        "configuration.MessageType",
        blank=True,
        related_name="roles",
    )

    class Meta:
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True),
                name="one_default_identity_role",
            )
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    site = models.ForeignKey(
        "configuration.Site",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="users")
    direct_capabilities = models.ManyToManyField(
        Capability,
        blank=True,
        related_name="direct_users",
    )
    message_groups = models.ManyToManyField(
        "configuration.MessageGroup",
        blank=True,
        related_name="users",
    )
    default_message_group = models.ForeignKey(
        "configuration.MessageGroup",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="default_for_users",
    )
    include_in_reports = models.BooleanField(default=True)
    imported_from_sap = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    local_auth_enabled = models.BooleanField(default=True)

    def clean(self) -> None:
        super().clean()
        if self.site_id and self.default_message_group_id:
            default_group = self.default_message_group
            if default_group and default_group.primary_group.site_id != self.site_id:
                raise ValidationError(
                    {"default_message_group": "Default group must belong to the user's site."}
                )
        if self.pk and self.default_message_group_id:
            if not self.message_groups.filter(pk=self.default_message_group_id).exists():
                raise ValidationError(
                    {"default_message_group": "Default group must be one of the memberships."}
                )


class SupervisorRelationship(models.Model):
    supervisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reportees")
    reportee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="supervisors")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("supervisor", "reportee", "starts_at"),
                name="unique_supervisor_period",
            )
        ]

    def __str__(self) -> str:
        return f"{self.supervisor} supervises {self.reportee}"

    def clean(self) -> None:
        super().clean()
        if self.supervisor_id == self.reportee_id:
            raise ValidationError("A user cannot supervise themselves.")
        if self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError("The end must be after the start.")


class IdentityPolicy(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    max_failed_logins = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(2)],
    )
    lockout_minutes = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
    )
    session_timeout_minutes = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(5)],
    )
    password_expiry_days = models.PositiveSmallIntegerField(
        default=90,
        validators=[MinValueValidator(1)],
    )
    password_warning_days = models.PositiveSmallIntegerField(default=14)
    password_min_length = models.PositiveSmallIntegerField(
        default=12,
        validators=[MinValueValidator(12)],
    )
    password_max_length = models.PositiveSmallIntegerField(
        default=128,
        validators=[MinValueValidator(64)],
    )
    approval_notification_email = models.EmailField(blank=True)
    policy_notification_email = models.EmailField(blank=True)
    account_lock_distribution_list = models.TextField(blank=True)

    def __str__(self) -> str:
        return "Identity security policy"

    def clean(self) -> None:
        super().clean()
        if self.password_warning_days >= self.password_expiry_days:
            raise ValidationError({"password_warning_days": "Warning must be shorter than expiry."})
        if self.password_min_length > self.password_max_length:
            raise ValidationError({"password_min_length": "Minimum exceeds maximum."})

    @classmethod
    def load(cls) -> IdentityPolicy:
        policy, _ = cls.objects.get_or_create(singleton=True)
        return policy
