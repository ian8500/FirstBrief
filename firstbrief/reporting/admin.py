from django.contrib import admin
from django.http import HttpRequest

from firstbrief.reporting.models import ImportChangeRecord, ReportingCohort, ReportRun

admin.site.register(ReportingCohort)
admin.site.register(ImportChangeRecord)


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("report_code", "actor", "status", "row_count", "created_at")
    readonly_fields = (
        "actor",
        "report_code",
        "catalogue_version",
        "criteria",
        "columns",
        "rows",
        "status",
        "row_count",
        "error",
        "created_at",
        "started_at",
        "completed_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: ReportRun | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: ReportRun | None = None) -> bool:
        return False
