from django.contrib import admin

from firstbrief.operations.models import (
    MessageAccessEvent,
    MessageReceipt,
    MessageViewSession,
    OperationalPolicy,
)

admin.site.register(OperationalPolicy)
admin.site.register(MessageReceipt)
admin.site.register(MessageViewSession)


@admin.register(MessageAccessEvent)
class MessageAccessEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "message", "event_type", "occurred_at")
    readonly_fields = (
        "user",
        "message",
        "event_type",
        "browser_session_key",
        "duration_seconds",
        "metadata",
        "occurred_at",
    )

    def has_add_permission(self, request: object) -> bool:
        return False

    def has_change_permission(self, request: object, obj: MessageAccessEvent | None = None) -> bool:
        return False

    def has_delete_permission(self, request: object, obj: MessageAccessEvent | None = None) -> bool:
        return False
