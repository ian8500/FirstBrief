from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from firstbrief.assurance.models import AuditEvent, PurgeRun, RetentionPolicy
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


def _months_ago(months: int) -> datetime:
    return timezone.now() - timedelta(days=months * 30)


def retention_candidates() -> list[str]:
    from firstbrief.messaging.models import Message

    policy = RetentionPolicy.load()
    archived = Message.objects.filter(
        status=Message.Status.ARCHIVED,
        updated_at__lt=_months_ago(policy.archived_months),
        purged_at__isnull=True,
    )
    expired = Message.objects.filter(
        status=Message.Status.EXPIRED,
        updated_at__lt=_months_ago(policy.expired_months),
        purged_at__isnull=True,
    )
    held = Message.objects.filter(legal_holds__active=True)
    return [
        str(pk) for pk in (archived | expired).exclude(pk__in=held).values_list("pk", flat=True)
    ]


def preview_purge(actor: User) -> PurgeRun:
    from firstbrief.identity.services import MANAGE_RETENTION, require_capability

    require_capability(actor, MANAGE_RETENTION)
    run = PurgeRun.objects.create(requested_by=actor, candidates=retention_candidates())
    record_event("retention.purge.previewed", actor=actor, subject=run)
    return run


@transaction.atomic
def approve_and_execute_purge(actor: User, run: PurgeRun) -> PurgeRun:
    from firstbrief.identity.services import MANAGE_RETENTION, require_capability
    from firstbrief.messaging.models import Message, MessageVersion

    require_capability(actor, MANAGE_RETENTION)
    locked = PurgeRun.objects.select_for_update().get(pk=run.pk)
    if locked.status != PurgeRun.Status.PREVIEW:
        raise ValidationError("Only a preview can be approved.")
    if RetentionPolicy.load().require_second_approver and locked.requested_by_id == actor.pk:
        raise PermissionDenied("A different authorised user must approve this purge.")
    eligible = set(retention_candidates())
    targets = [pk for pk in locked.candidates if pk in eligible]
    MessageVersion.objects.filter(message_id__in=targets).update(
        summary="[Purged under retention policy]",
        text_content="",
        searchable_content="",
    )
    Message.objects.filter(pk__in=targets).update(purged_at=timezone.now())
    evidence = json.dumps(sorted(targets), separators=(",", ":")).encode()
    locked.approved_by = actor
    locked.status = PurgeRun.Status.COMPLETE
    locked.completed_at = timezone.now()
    locked.evidence_sha256 = hashlib.sha256(evidence).hexdigest()
    locked.save(
        update_fields=(
            "approved_by",
            "status",
            "completed_at",
            "evidence_sha256",
        )
    )
    record_event(
        "retention.purge.completed",
        actor=actor,
        subject=locked,
        after={"count": len(targets), "sha256": locked.evidence_sha256},
    )
    return locked


def continuity_export() -> tuple[bytes, str]:
    from firstbrief.messaging.models import Message
    from firstbrief.reporting.models import ReportRun
    from firstbrief.sapimport.models import ImportBatch

    data = {
        "generated_at": timezone.now().isoformat(),
        "messages": list(
            Message.objects.order_by("message_id").values(
                "message_id", "status", "current_version_number", "purged_at"
            )
        ),
        "reports": list(
            ReportRun.objects.order_by("created_at").values(
                "id", "report_code", "status", "row_count", "completed_at"
            )
        ),
        "imports": list(
            ImportBatch.objects.order_by("staged_at").values(
                "id", "filename", "content_sha256", "status"
            )
        ),
    }
    payload = json.dumps(data, default=str, sort_keys=True, separators=(",", ":")).encode()
    return payload, hashlib.sha256(payload).hexdigest()
