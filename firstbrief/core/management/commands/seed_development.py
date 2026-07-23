"""Idempotently load non-sensitive development fixtures."""

from __future__ import annotations

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Load safe development seed data"

    def handle(self, *args: object, **options: object) -> None:
        if settings.ENVIRONMENT != "development":
            raise CommandError("Development fixtures may only be loaded in development")
        call_command("loaddata", "development", verbosity=0)
        self.stdout.write(self.style.SUCCESS("Development fixtures loaded"))
