from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firstbrief.assurance.models import AuditEvent
from firstbrief.core.middleware import get_correlation_id

if TYPE_CHECKING:
    from firstbrief.identity.models import User


def record_event(
    action: str,
    *,
    actor: User | None = None,
    subject: object | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str = "",
) -> AuditEvent:
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=subject.__class__.__name__ if subject else "system",
        object_id=str(getattr(subject, "pk", "")) if subject else "",
        correlation_id=get_correlation_id(),
        before=before or {},
        after=after or {},
        reason=reason,
    )
