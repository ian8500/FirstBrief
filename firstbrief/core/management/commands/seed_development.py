"""Idempotently load non-sensitive development fixtures."""

from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from firstbrief.configuration.models import (
    MessageGroup,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Site,
)
from firstbrief.identity.models import Capability, IdentityPolicy, Role, User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    CREATE_MESSAGES,
    MANAGE_CONFIGURATION,
    MANAGE_IDENTITY_SETTINGS,
    MANAGE_MESSAGES,
    MANAGE_RETENTION,
    MANAGE_ROLES,
    MANAGE_SAP_IMPORTS,
    MANAGE_USERS,
    SEE_ALL_PMG,
    VIEW_AUDIT_HISTORY,
    VIEW_REPORTS,
)
from firstbrief.notifications.models import NotificationPolicy
from firstbrief.operations.models import OperationalPolicy


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
        _botd, _ = MessageType.objects.update_or_create(
            code="botd",
            defaults={
                "name": "Brief of the Day",
                "default_content_type": MessageType.ContentType.TEXT,
                "requires_approval": False,
                "has_subtypes": False,
                "has_effective_date": False,
            },
        )
        instruction, _ = MessageType.objects.update_or_create(
            code="instruction",
            defaults={
                "name": "Instruction",
                "default_content_type": MessageType.ContentType.PDF,
                "requires_approval": True,
                "has_subtypes": True,
                "has_effective_date": True,
            },
        )
        MessageSubType.objects.get_or_create(
            code="general-instruction",
            defaults={
                "name": "General Instruction",
                "primary_group": primary_group,
                "message_type": instruction,
                "minimum_validity_days": 1,
                "maximum_validity_days": 365,
            },
        )
        capabilities = [
            Capability.objects.get_or_create(codename=code, defaults={"name": name})[0]
            for code, name in (
                (MANAGE_USERS, "Manage users"),
                (MANAGE_ROLES, "Manage roles"),
                (MANAGE_IDENTITY_SETTINGS, "Manage identity settings"),
                (MANAGE_CONFIGURATION, "Manage configuration"),
                (CREATE_MESSAGES, "Create messages"),
                (APPROVE_MESSAGES, "Approve messages"),
                (MANAGE_MESSAGES, "Manage messages"),
                (SEE_ALL_PMG, "See all primary message groups"),
                (VIEW_AUDIT_HISTORY, "View message audit history"),
                (VIEW_REPORTS, "View compliance reports"),
                (MANAGE_SAP_IMPORTS, "Manage SAP imports"),
                (MANAGE_RETENTION, "Manage retention and continuity"),
            )
        ]
        role, _ = Role.objects.get_or_create(name="System administrator")
        role.capabilities.set(capabilities)
        role.message_types.set(MessageType.objects.all())
        IdentityPolicy.load()
        NotificationPolicy.load()
        OperationalPolicy.load()

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
