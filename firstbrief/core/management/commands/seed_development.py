"""Idempotently load non-sensitive development fixtures."""

from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from firstbrief.configuration.models import MessageGroup, MessageType, PrimaryMessageGroup, Site
from firstbrief.identity.models import Capability, IdentityPolicy, Role, User
from firstbrief.identity.services import (
    MANAGE_CONFIGURATION,
    MANAGE_IDENTITY_SETTINGS,
    MANAGE_ROLES,
    MANAGE_USERS,
    SEE_ALL_PMG,
)


class Command(BaseCommand):
    help = "Load safe development seed data"

    def handle(self, *args: object, **options: object) -> None:
        if settings.ENVIRONMENT != "development":
            raise CommandError("Development fixtures may only be loaded in development")
        call_command("loaddata", "development", verbosity=0)
        self.seed_identity()
        self.stdout.write(self.style.SUCCESS("Development fixtures loaded"))

    def seed_identity(self) -> None:
        site, _ = Site.objects.get_or_create(code="demo", defaults={"name": "Demo Site"})
        primary_group, _ = PrimaryMessageGroup.objects.get_or_create(
            code="demo-pmg",
            defaults={"name": "Demo Primary Message Group", "site": site},
        )
        MessageGroup.objects.get_or_create(
            code="demo-operations",
            defaults={"name": "Demo Operations", "primary_group": primary_group},
        )
        for code, name in (("botd", "Brief of the Day"), ("instruction", "Instruction")):
            MessageType.objects.get_or_create(code=code, defaults={"name": name})
        capabilities = [
            Capability.objects.get_or_create(codename=code, defaults={"name": name})[0]
            for code, name in (
                (MANAGE_USERS, "Manage users"),
                (MANAGE_ROLES, "Manage roles"),
                (MANAGE_IDENTITY_SETTINGS, "Manage identity settings"),
                (MANAGE_CONFIGURATION, "Manage configuration"),
                (SEE_ALL_PMG, "See all primary message groups"),
            )
        ]
        role, _ = Role.objects.get_or_create(name="System administrator")
        role.capabilities.set(capabilities)
        role.message_types.set(MessageType.objects.all())
        IdentityPolicy.load()

        password = os.environ.get("FIRSTBRIEF_DEVELOPMENT_ADMIN_PASSWORD")
        if not password:
            self.stdout.write(
                "No demo administrator created; set FIRSTBRIEF_DEVELOPMENT_ADMIN_PASSWORD."
            )
            return
        user, _ = User.objects.get_or_create(
            username="demo-admin",
            defaults={
                "first_name": "Demo",
                "last_name": "Administrator",
                "email": "demo-admin@example.invalid",
                "site": site,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        validate_password(password, user)
        user.set_password(password)
        user.password_changed_at = timezone.now()
        user.save()
        user.roles.add(role)
