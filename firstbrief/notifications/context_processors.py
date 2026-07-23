from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_MESSAGES, has_capability


def notification_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    return {
        "can_manage_notifications": isinstance(user, User) and has_capability(user, MANAGE_MESSAGES)
    }
