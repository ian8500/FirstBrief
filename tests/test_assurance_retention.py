from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from firstbrief.assurance.models import LegalHold, RetentionPolicy
from firstbrief.assurance.services import (
    approve_and_execute_purge,
    continuity_export,
    preview_purge,
)
from firstbrief.configuration.models import MessageType
from firstbrief.identity.models import Capability, User
from firstbrief.identity.services import MANAGE_RETENTION
from firstbrief.messaging.models import Message, MessageVersion

pytestmark = pytest.mark.django_db


@pytest.fixture
def retention_data() -> dict[str, Any]:
    capability = Capability.objects.create(codename=MANAGE_RETENTION, name="Manage retention")
    requester = User.objects.create_user(username="retention-one", password="Safe-test-42!")
    approver = User.objects.create_user(username="retention-two", password="Safe-test-42!")
    requester.direct_capabilities.add(capability)
    approver.direct_capabilities.add(capability)
    message_type = MessageType.objects.create(
        code="retention-text",
        name="Retention text",
        default_content_type=MessageType.ContentType.TEXT,
    )
    message = Message.objects.create(
        message_id="RETENTION-001",
        kind=Message.Kind.BOTD,
        message_type=message_type,
        originator=requester,
        status=Message.Status.ARCHIVED,
    )
    MessageVersion.objects.create(
        message=message,
        version_number=1,
        title="Retained title",
        summary="Sensitive summary",
        text_content="Sensitive content",
        release_at=timezone.now() - timedelta(days=400),
        expiry_at=timezone.now() - timedelta(days=300),
        created_by=requester,
    )
    Message.objects.filter(pk=message.pk).update(updated_at=timezone.now() - timedelta(days=100))
    policy = RetentionPolicy.load()
    policy.archived_months = 1
    policy.save()
    return {"requester": requester, "approver": approver, "message": message}


def test_preview_requires_two_people_and_purges_content(
    retention_data: dict[str, Any],
) -> None:
    run = preview_purge(retention_data["requester"])
    assert str(retention_data["message"].pk) in run.candidates
    with pytest.raises(PermissionDenied):
        approve_and_execute_purge(retention_data["requester"], run)
    completed = approve_and_execute_purge(retention_data["approver"], run)
    retention_data["message"].refresh_from_db()
    assert completed.evidence_sha256
    assert retention_data["message"].purged_at is not None
    assert retention_data["message"].current_version.text_content == ""


def test_legal_hold_excludes_message_and_export_has_checksum(
    retention_data: dict[str, Any],
) -> None:
    LegalHold.objects.create(
        name="Investigation",
        reason="Required evidence",
        message=retention_data["message"],
        created_by=retention_data["requester"],
    )
    assert preview_purge(retention_data["requester"]).candidates == []
    payload, digest = continuity_export()
    assert b"RETENTION-001" in payload
    assert len(digest) == 64
