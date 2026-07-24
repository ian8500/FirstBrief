from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_SAP_IMPORTS, has_capability


def import_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    return {
        "can_manage_imports": isinstance(user, User) and has_capability(user, MANAGE_SAP_IMPORTS)
    }
