from django.contrib import admin

from firstbrief.assurance.models import AuditEvent, LegalHold, PurgeRun, RetentionPolicy

admin.site.register((RetentionPolicy, LegalHold, PurgeRun))


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("occurred_at", "action", "object_type", "object_id", "actor")
    readonly_fields = (
        "actor",
        "action",
        "object_type",
        "object_id",
        "occurred_at",
        "correlation_id",
        "reason",
        "before",
        "after",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: object | None = None) -> bool:
        return False
