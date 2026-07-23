from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from firstbrief.identity.models import (
    Capability,
    IdentityPolicy,
    Role,
    SupervisorRelationship,
    User,
)


@admin.register(User)
class FirstBriefUserAdmin(UserAdmin):  # type: ignore[type-arg]
    fieldsets = (
        *UserAdmin.fieldsets,  # type: ignore[misc]
        (
            "FirstBrief access",
            {
                "fields": (
                    "site",
                    "roles",
                    "direct_capabilities",
                    "message_groups",
                    "default_message_group",
                    "include_in_reports",
                    "imported_from_sap",
                    "local_auth_enabled",
                    "must_change_password",
                    "password_changed_at",
                    "failed_login_count",
                    "locked_until",
                )
            },
        ),
    )
    filter_horizontal = (
        *UserAdmin.filter_horizontal,
        "roles",
        "direct_capabilities",
        "message_groups",
    )
    list_display = (
        "username",
        "first_name",
        "last_name",
        "site",
        "include_in_reports",
        "is_active",
    )


admin.site.register((Capability, Role, SupervisorRelationship, IdentityPolicy))
