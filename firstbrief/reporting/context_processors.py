"""Navigation permission for reporting."""

from django.http import HttpRequest

from firstbrief.identity.models import User
from firstbrief.identity.services import VIEW_REPORTS, has_capability


def reporting_access(request: HttpRequest) -> dict[str, bool]:
    user = request.user
    return {"can_view_reports": isinstance(user, User) and has_capability(user, VIEW_REPORTS)}
