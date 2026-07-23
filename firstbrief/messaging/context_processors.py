from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    CREATE_MESSAGES,
    MANAGE_MESSAGES,
    has_capability,
)


def message_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    allowed = isinstance(user, User) and any(
        has_capability(user, capability)
        for capability in (CREATE_MESSAGES, APPROVE_MESSAGES, MANAGE_MESSAGES)
    )
    return {"can_manage_messages": allowed}
