"""Configurable message taxonomy and routing references."""

from __future__ import annotations

from typing import ClassVar

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError


class ActiveReference(models.Model):
    code = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=160)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Site(ActiveReference):
    pass


class PrimaryMessageGroup(ActiveReference):
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="primary_groups")


class MessageType(ActiveReference):
    class ContentType(models.TextChoices):
        TEXT = "text", "Text"
        PDF = "pdf", "PDF"

    class ViewMode(models.TextChoices):
        FULL = "full", "Full page"
        PANEL = "panel", "Side panel"

    class MenuView(models.TextChoices):
        MANDATORY = "mandatory", "Mandatory"
        OTHER = "other", "Other"
        BOTH = "both", "Both"

    default_content_type = models.CharField(
        max_length=8, choices=ContentType.choices, default=ContentType.TEXT
    )
    view_mode = models.CharField(max_length=12, choices=ViewMode.choices, default=ViewMode.FULL)
    menu_view = models.CharField(max_length=12, choices=MenuView.choices, default=MenuView.BOTH)
    display_at_logon = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)
    searchable = models.BooleanField(default=True)
    has_subtypes = models.BooleanField(default=False)
    has_effective_date = models.BooleanField(default=False)

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.roles.exists() or self.subtypes.exists() or self.group_types.exists():
            raise ProtectedError("Message type is in use and cannot be deleted.", {self})
        return super().delete(using=using, keep_parents=keep_parents)


class MessageGroupType(ActiveReference):
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    exclusive_membership = models.BooleanField(default=False)
    allowed_message_types = models.ManyToManyField(
        MessageType,
        blank=True,
        related_name="group_types",
        help_text="Leave empty to allow all message types.",
    )

    class Meta(ActiveReference.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=F("id")),
                name="group_type_not_own_parent",
            )
        ]

    def clean(self) -> None:
        super().clean()
        ancestor = self.parent
        while ancestor:
            if ancestor.pk == self.pk:
                raise ValidationError({"parent": "A group type cannot be its own ancestor."})
            ancestor = ancestor.parent

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.children.exists() or self.message_groups.exists():
            raise ProtectedError("Group type has children or message groups.", {self})
        return super().delete(using=using, keep_parents=keep_parents)


class Sector(ActiveReference):
    identification = models.CharField(max_length=100)
    primary_group = models.ForeignKey(
        PrimaryMessageGroup, on_delete=models.PROTECT, related_name="sectors"
    )

    class Meta(ActiveReference.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("primary_group", "identification"),
                name="unique_sector_identification_per_pmg",
            )
        ]


class MessageGroup(ActiveReference):
    primary_group = models.ForeignKey(
        PrimaryMessageGroup,
        on_delete=models.PROTECT,
        related_name="message_groups",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    group_type = models.ForeignKey(
        MessageGroupType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="message_groups",
    )
    sectors = models.ManyToManyField(Sector, blank=True, related_name="message_groups")

    class Meta(ActiveReference.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(parent__isnull=True) | ~Q(parent=F("id")),
                name="message_group_not_own_parent",
            )
        ]

    def clean(self) -> None:
        super().clean()
        ancestor = self.parent
        while ancestor:
            if ancestor.pk == self.pk:
                raise ValidationError({"parent": "A message group cannot be its own ancestor."})
            if self.primary_group_id and ancestor.primary_group_id != self.primary_group_id:
                raise ValidationError({"parent": "Parent must belong to the same primary group."})
            ancestor = ancestor.parent

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.children.exists() or self.users.exists() or self.default_for_users.exists():
            raise ProtectedError("Message group has children or user memberships.", {self})
        messages = getattr(self, "messages", None)
        if messages is not None and messages.exists():
            raise ProtectedError("Message group has messages.", {self})
        return super().delete(using=using, keep_parents=keep_parents)


class EmailDistribution(ActiveReference):
    email_address = models.EmailField()
    use_as_email = models.BooleanField(default=True)

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        if self.subtypes.exists():
            raise ProtectedError("Distribution is linked to a message subtype.", {self})
        return super().delete(using=using, keep_parents=keep_parents)


class MessageSubType(ActiveReference):
    primary_group = models.ForeignKey(
        PrimaryMessageGroup, on_delete=models.PROTECT, related_name="message_subtypes"
    )
    message_type = models.ForeignKey(
        MessageType, on_delete=models.PROTECT, related_name="subtypes"
    )
    minimum_validity_days = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    maximum_validity_days = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    email_distributions = models.ManyToManyField(
        EmailDistribution, blank=True, related_name="subtypes"
    )

    class Meta(ActiveReference.Meta):
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(maximum_validity_days__gte=F("minimum_validity_days")),
                name="subtype_validity_min_lte_max",
            ),
            models.UniqueConstraint(
                fields=("primary_group", "message_type", "name"),
                name="unique_subtype_name_per_pmg_type",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.maximum_validity_days < self.minimum_validity_days:
            raise ValidationError(
                {"maximum_validity_days": "Maximum validity must be at least the minimum."}
            )
        if self.message_type_id and not self.message_type.has_subtypes:
            raise ValidationError(
                {"message_type": "Enable subtypes on the selected message type first."}
            )

    def delete(
        self, using: str | None = None, keep_parents: bool = False
    ) -> tuple[int, dict[str, int]]:
        messages = getattr(self, "messages", None)
        if messages is not None and messages.exists():
            raise ProtectedError("Message subtype has messages.", {self})
        return super().delete(using=using, keep_parents=keep_parents)
