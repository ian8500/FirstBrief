from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import (
    MANAGE_RETENTION,
    VIEW_AUDIT_HISTORY,
    has_capability,
)


def assurance_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    return {
        "can_view_assurance": isinstance(user, User)
        and (has_capability(user, VIEW_AUDIT_HISTORY) or has_capability(user, MANAGE_RETENTION))
    }
