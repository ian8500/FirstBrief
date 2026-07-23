"""Minimal configuration references required by identity and access control."""

from django.db import models


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


class MessageGroup(ActiveReference):
    primary_group = models.ForeignKey(
        PrimaryMessageGroup,
        on_delete=models.PROTECT,
        related_name="message_groups",
    )


class MessageType(ActiveReference):
    pass
