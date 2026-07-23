"""Stable message aggregates, immutable versions and lifecycle evidence."""

from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class PreservedMessageQuerySet(models.QuerySet["Message"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Messages are preserved; use a lifecycle command.")


class PreservedVersionQuerySet(models.QuerySet["MessageVersion"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError("Message versions are immutable and cannot be deleted.")


class Message(models.Model):
    class Kind(models.TextChoices):
        BOTD = "botd", "Brief of the Day"
        INSTRUCTION = "instruction", "Instruction"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft / Unapproved"
        APPROVED_PENDING_RELEASE = "approved_pending_release", "Approved pending release"
        RELEASED_PENDING_EFFECTIVE = "released_pending_effective", "Released pending effective"
        EFFECTIVE = "effective", "Effective"
        EXPIRED = "expired", "Expired"
        ARCHIVED = "archived", "Archived"
        WITHDRAWN = "withdrawn", "Withdrawn"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_id = models.SlugField(max_length=80, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    message_type = models.ForeignKey(
        "configuration.MessageType", on_delete=models.PROTECT, related_name="messages"
    )
    subtype = models.ForeignKey(
        "configuration.MessageSubType",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="messages",
    )
    originator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="originated_messages"
    )
    approvers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="messages_to_approve"
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    lock_version = models.PositiveIntegerField(default=1)
    current_version_number = models.PositiveIntegerField(default=1)
    archive_on_expiry = models.BooleanField(default=True)
    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseded_by",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PreservedMessageQuerySet.as_manager()

    class Meta:
        ordering = ("-updated_at",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("message_id",), name="message_id_lookup"),
            models.Index(fields=("status", "updated_at"), name="message_status_updated"),
        ]

    def __str__(self) -> str:
        return self.message_id

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("message_id", flat=True)
                .first()
            )
            if original is not None and original != self.message_id:
                raise ValidationError({"message_id": "Message ID is immutable."})
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Messages are preserved; use a lifecycle command.")

    @property
    def current_version(self) -> MessageVersion:
        return self.versions.get(version_number=self.current_version_number)

    def clean(self) -> None:
        super().clean()
        if self.kind == self.Kind.BOTD and self.message_type.default_content_type != "text":
            raise ValidationError({"message_type": "BOTD requires a text message type."})
        if self.kind == self.Kind.INSTRUCTION and self.message_type.default_content_type != "pdf":
            raise ValidationError({"message_type": "Instruction requires a PDF message type."})
        if self.subtype_id:
            subtype = self.subtype
            if subtype is not None and subtype.message_type_id != self.message_type_id:
                raise ValidationError({"subtype": "Subtype must belong to the message type."})
        elif self.message_type_id and self.message_type.has_subtypes:
            raise ValidationError({"subtype": "This message type requires a subtype."})


class MessageVersion(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=240)
    summary = models.TextField(blank=True)
    text_content = models.TextField(blank=True)
    release_at = models.DateTimeField()
    effective_at = models.DateTimeField(null=True, blank=True)
    expiry_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="message_versions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PreservedVersionQuerySet.as_manager()

    class Meta:
        ordering = ("message", "version_number")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("message", "version_number"), name="unique_message_version"
            ),
            models.CheckConstraint(
                condition=Q(expiry_at__gt=F("release_at")), name="message_expiry_after_release"
            ),
            models.CheckConstraint(
                condition=Q(effective_at__isnull=True) | Q(expiry_at__gte=F("effective_at")),
                name="message_expiry_not_before_effective",
            ),
            models.CheckConstraint(
                condition=Q(effective_at__isnull=True) | Q(effective_at__gte=F("release_at")),
                name="message_effective_not_before_release",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.message.message_id} v{self.version_number}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk and self.message.status != Message.Status.DRAFT:
            raise ValidationError("Approved message versions are immutable; create a new version.")
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        raise ValidationError("Message versions are immutable and cannot be deleted.")

    def clean(self) -> None:
        super().clean()
        if self.expiry_at <= self.release_at:
            raise ValidationError({"expiry_at": "Expiry must be after release."})
        if self.effective_at and self.expiry_at < self.effective_at:
            raise ValidationError({"expiry_at": "Expiry cannot be before effective time."})
        if self.effective_at and self.effective_at < self.release_at:
            raise ValidationError({"effective_at": "Effective time cannot be before release."})
        if self.message.message_type.has_effective_date and not self.effective_at:
            raise ValidationError({"effective_at": "This message type requires an effective time."})
        if not self.message.message_type.has_effective_date and self.effective_at:
            raise ValidationError(
                {"effective_at": "This message type does not use an effective time."}
            )
        if (
            self.message.message_type.default_content_type == "text"
            and not self.text_content.strip()
        ):
            raise ValidationError({"text_content": "Text content is required."})


class MessageAudienceRight(models.Model):
    class Right(models.TextChoices):
        PROHIBITED = "prohibited", "Prohibited"
        ALLOWED = "allowed", "Allowed"
        MANDATORY = "mandatory", "Mandatory"

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="audience_rights")
    message_group = models.ForeignKey(
        "configuration.MessageGroup", on_delete=models.PROTECT, related_name="message_rights"
    )
    right = models.CharField(max_length=12, choices=Right.choices)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("message", "message_group"), name="unique_message_group_right"
            )
        ]

    def __str__(self) -> str:
        return f"{self.message.message_id}: {self.message_group} ({self.get_right_display()})"


class Approval(models.Model):
    message = models.ForeignKey(Message, on_delete=models.PROTECT, related_name="approvals")
    version = models.ForeignKey(
        MessageVersion, on_delete=models.PROTECT, related_name="approvals"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="message_approvals"
    )
    justification = models.TextField()
    validity_justification = models.TextField(blank=True)
    approved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.message.message_id} approved by {self.actor}"


class MessageStatusHistory(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=32, choices=Message.Status.choices, blank=True)
    to_status = models.CharField(max_length=32, choices=Message.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="message_status_changes",
    )
    reason = models.TextField(blank=True)
    aggregate_version = models.PositiveIntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "pk")

    def __str__(self) -> str:
        return (
            f"{self.message.message_id}: "
            f"{self.get_from_status_display()} → {self.get_to_status_display()}"
        )


class LifecycleCommand(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="commands")
    idempotency_key = models.UUIDField()
    command = models.SlugField(max_length=40)
    resulting_status = models.CharField(max_length=32, choices=Message.Status.choices)
    aggregate_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("message", "idempotency_key"), name="unique_message_command_key"
            )
        ]

    def __str__(self) -> str:
        return f"{self.message.message_id}: {self.command}"


class FileAsset(models.Model):
    class Role(models.TextChoices):
        DISPLAY = "display", "Display PDF"
        PRINT = "print", "Print PDF"

    class ScanStatus(models.TextChoices):
        QUARANTINED = "quarantined", "Quarantined"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        ERROR = "error", "Scan error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(MessageVersion, on_delete=models.PROTECT, related_name="files")
    role = models.CharField(max_length=12, choices=Role.choices)
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=255, unique=True, editable=False)
    content_type = models.CharField(max_length=100)
    byte_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    scan_status = models.CharField(
        max_length=16, choices=ScanStatus.choices, default=ScanStatus.QUARANTINED
    )
    scan_detail = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_message_files"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("version", "role"), name="one_file_per_version_role")
        ]

    def __str__(self) -> str:
        return f"{self.version}: {self.get_role_display()}"


class MessagePolicy(models.Model):
    singleton = models.BooleanField(default=True, unique=True, editable=False)
    enforce_pdf_filename_match = models.BooleanField(default=False)
    maximum_pdf_bytes = models.PositiveIntegerField(default=10 * 1024 * 1024)

    def __str__(self) -> str:
        return "Message authoring policy"

    @classmethod
    def load(cls) -> MessagePolicy:
        policy, _ = cls.objects.get_or_create(singleton=True)
        return policy
