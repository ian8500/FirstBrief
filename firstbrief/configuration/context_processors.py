from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, has_capability


def configuration_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    return {
        "can_manage_configuration": isinstance(user, User)
        and has_capability(user, MANAGE_CONFIGURATION)
    }
