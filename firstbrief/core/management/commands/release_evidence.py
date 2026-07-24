"""Emit deterministic release evidence for operations and CI."""

from django.core.management.base import BaseCommand
from django.db import connection

from firstbrief.assurance.models import AuditEvent, LegalHold, PurgeRun
from firstbrief.messaging.models import Message
from firstbrief.reporting.models import ReportRun
from firstbrief.sapimport.models import ImportBatch


class Command(BaseCommand):
    help = "Report release-candidate evidence counts and database connectivity."

    def handle(self, *args: object, **options: object) -> None:
        connection.ensure_connection()
        evidence = {
            "database": connection.vendor,
            "messages": Message.objects.count(),
            "audit_events": AuditEvent.objects.count(),
            "report_runs": ReportRun.objects.count(),
            "import_batches": ImportBatch.objects.count(),
            "active_legal_holds": LegalHold.objects.filter(active=True).count(),
            "purge_runs": PurgeRun.objects.count(),
        }
        for key, value in evidence.items():
            self.stdout.write(f"{key}={value}")
        self.stdout.write(self.style.SUCCESS("release_evidence=ready"))
