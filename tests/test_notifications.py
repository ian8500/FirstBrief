from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client
from django.utils import timezone
from pypdf import PdfWriter

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.models import (
    EmailDistribution,
    MessageGroup,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Site,
)
from firstbrief.identity.models import Capability, IdentityPolicy, User
from firstbrief.identity.services import MANAGE_MESSAGES
from firstbrief.messaging.files import attach_message_pdfs
from firstbrief.messaging.models import Message, MessageAudienceRight
from firstbrief.messaging.scanning import ScanResult
from firstbrief.messaging.services import approve_message, create_message, revise_message
from firstbrief.notifications.models import (
    LifecycleJob,
    NotificationJob,
    NotificationPolicy,
    OutboxEvent,
)
from firstbrief.notifications.services import (
    apply_quiet_hours,
    deliver_notifications,
    manual_resend,
    process_due_lifecycle,
    process_outbox,
)
from firstbrief.notifications.tasks import (
    deliver_notifications_task,
    process_lifecycle_task,
    process_outbox_task,
)

pytestmark = pytest.mark.django_db


class CleanScanner:
    def scan(self, path: Path) -> ScanResult:
        return ScanResult(True, "clean")


@pytest.fixture
def orchestration_data() -> dict[str, Any]:
    site = Site.objects.create(code="schedule-site", name="Schedule Site")
    pmg = PrimaryMessageGroup.objects.create(code="schedule-pmg", name="Schedule PMG", site=site)
    group = MessageGroup.objects.create(
        code="schedule-group", name="Schedule Group", primary_group=pmg
    )
    botd_type = MessageType.objects.create(
        code="scheduled-botd",
        name="Scheduled BOTD",
        default_content_type=MessageType.ContentType.TEXT,
    )
    instruction_type = MessageType.objects.create(
        code="scheduled-instruction",
        name="Scheduled Instruction",
        default_content_type=MessageType.ContentType.PDF,
        requires_approval=True,
        has_subtypes=True,
        has_effective_date=True,
    )
    subtype = MessageSubType.objects.create(
        code="scheduled-general",
        name="Scheduled General",
        primary_group=pmg,
        message_type=instruction_type,
        maximum_validity_days=30,
    )
    distribution = EmailDistribution.objects.create(
        code="scheduled-approvers",
        name="Scheduled Approvers",
        email_address="distribution@example.test",
        use_as_email=True,
    )
    subtype.email_distributions.add(distribution)
    actor = User.objects.create_superuser(
        username="schedule-admin",
        password="Safe-test-42!",
        email="admin@example.test",
    )
    approver = User.objects.create_user(
        username="schedule-approver",
        password="Safe-test-42!",
        email="approver@example.test",
    )
    return {
        "site": site,
        "group": group,
        "botd_type": botd_type,
        "instruction_type": instruction_type,
        "subtype": subtype,
        "distribution": distribution,
        "actor": actor,
        "approver": approver,
    }


def _pdf(name: str) -> SimpleUploadedFile:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return SimpleUploadedFile(name, output.getvalue(), content_type="application/pdf")


def _botd(data: dict[str, Any], message_id: str = "SCHEDULE-BOTD") -> Message:
    now = timezone.now()
    return create_message(
        actor=data["actor"],
        message_id=message_id,
        kind=Message.Kind.BOTD,
        message_type=data["botd_type"],
        subtype=None,
        title="Scheduled brief",
        summary="",
        text_content="Scheduled content",
        release_at=now + timedelta(hours=1),
        effective_at=None,
        expiry_at=now + timedelta(hours=3),
        archive_on_expiry=True,
        group_rights={data["group"].pk: MessageAudienceRight.Right.ALLOWED},
    )


def _instruction(
    data: dict[str, Any], message_id: str = "SCHEDULE-INS", *, files: bool = False
) -> Message:
    now = timezone.now()
    message = create_message(
        actor=data["actor"],
        message_id=message_id,
        kind=Message.Kind.INSTRUCTION,
        message_type=data["instruction_type"],
        subtype=data["subtype"],
        title="Scheduled instruction",
        summary="",
        text_content="",
        release_at=now + timedelta(hours=1),
        effective_at=now + timedelta(hours=2),
        expiry_at=now + timedelta(days=2),
        archive_on_expiry=True,
        group_rights={data["group"].pk: MessageAudienceRight.Right.MANDATORY},
        approvers=[data["approver"]],
    )
    if files:
        attach_message_pdfs(
            version=message.current_version,
            display_upload=_pdf(f"{message_id}-display.pdf"),
            print_upload=_pdf(f"{message_id}-print.pdf"),
            actor=data["actor"],
            scanner=CleanScanner(),
        )
    return message


def test_creation_transaction_writes_outbox_and_lifecycle_schedule(
    orchestration_data: dict[str, Any],
) -> None:
    message = _instruction(orchestration_data)
    event = OutboxEvent.objects.get(topic="message-created")
    assert event.payload["message_pk"] == str(message.pk)
    assert event.payload["recipients"] == [
        "approver@example.test",
        "distribution@example.test",
    ]
    assert set(
        LifecycleJob.objects.filter(message=message).values_list("transition", flat=True)
    ) == {
        LifecycleJob.Transition.RELEASE,
        LifecycleJob.Transition.EFFECTIVE,
        LifecycleJob.Transition.EXPIRE,
        LifecycleJob.Transition.ARCHIVE,
        LifecycleJob.Transition.RETENTION_REVIEW,
        LifecycleJob.Transition.UNAPPROVED_ALERT,
    }


def test_outer_rollback_removes_message_outbox_and_schedule(
    orchestration_data: dict[str, Any],
) -> None:
    with pytest.raises(RuntimeError), transaction.atomic():
        _botd(orchestration_data, "ROLLBACK-BOTD")
        raise RuntimeError("force rollback")
    assert not Message.objects.filter(message_id="ROLLBACK-BOTD").exists()
    assert not OutboxEvent.objects.exists()
    assert not LifecycleJob.objects.exists()


def test_outbox_materialises_one_deduplicated_notification(
    orchestration_data: dict[str, Any],
) -> None:
    message = _instruction(orchestration_data)
    now = timezone.now() + timedelta(minutes=1)
    assert process_outbox(now=now) == 1
    assert process_outbox(now=now) == 0
    job = NotificationJob.objects.get()
    assert job.kind == NotificationJob.Kind.CREATED
    assert job.recipients == ["approver@example.test", "distribution@example.test"]
    assert job.subject == f"FirstBrief instruction awaiting approval: {message.message_id}"
    assert "Scheduled instruction is awaiting approval." in job.body
    assert "Release:" in job.body
    assert OutboxEvent.objects.get().status == OutboxEvent.Status.PUBLISHED


def test_notification_delivery_sends_once_and_audits(
    orchestration_data: dict[str, Any],
) -> None:
    message = _instruction(orchestration_data)
    process_outbox(now=timezone.now() + timedelta(minutes=1))
    assert deliver_notifications(now=timezone.now() + timedelta(minutes=2)) == 1
    assert deliver_notifications(now=timezone.now() + timedelta(minutes=2)) == 0
    assert len(mail.outbox) == 1
    assert message.message_id in mail.outbox[0].subject
    job = NotificationJob.objects.get()
    assert job.status == NotificationJob.Status.SENT
    assert AuditEvent.objects.filter(action="notification.sent").exists()


def test_delivery_retries_then_moves_to_visible_dead_letter(
    orchestration_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _instruction(orchestration_data)
    process_outbox(now=timezone.now() + timedelta(minutes=1))
    policy = NotificationPolicy.load()
    policy.maximum_attempts = 2
    policy.retry_delay_minutes = 1
    policy.save()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("mail server unavailable")

    monkeypatch.setattr("firstbrief.notifications.services.send_mail", fail)
    first = timezone.now() + timedelta(minutes=2)
    assert deliver_notifications(now=first) == 0
    job = NotificationJob.objects.get()
    assert job.status == NotificationJob.Status.PENDING
    assert job.next_attempt_at == first + timedelta(minutes=1)
    assert deliver_notifications(now=first + timedelta(minutes=1)) == 0
    job.refresh_from_db()
    assert job.status == NotificationJob.Status.DEAD
    assert job.attempts == 2
    assert "mail server unavailable" in job.last_error


def test_quiet_hours_handle_overnight_dst_boundary() -> None:
    policy = NotificationPolicy(
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
        timezone_name="Europe/London",
    )
    value = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    assert apply_quiet_hours(value, policy) == datetime(2026, 3, 29, 6, 0, tzinfo=UTC)
    daytime = datetime(2026, 3, 29, 12, 0, tzinfo=UTC)
    assert apply_quiet_hours(daytime, policy) == daytime


def test_delivery_rechecks_quiet_hours_after_worker_delay(
    orchestration_data: dict[str, Any],
) -> None:
    _instruction(orchestration_data, "QUIET-DELIVERY")
    process_outbox(now=timezone.now() + timedelta(minutes=1))
    policy = NotificationPolicy.load()
    policy.quiet_hours_start = time(22, 0)
    policy.quiet_hours_end = time(7, 0)
    policy.timezone_name = "Europe/London"
    policy.save()
    job = NotificationJob.objects.get()
    quiet_time = datetime.combine(job.next_attempt_at.date(), time(22, 30), tzinfo=UTC)
    expected_delivery = apply_quiet_hours(quiet_time, policy)

    assert deliver_notifications(now=quiet_time) == 0
    job.refresh_from_db()
    assert job.status == NotificationJob.Status.PENDING
    assert job.attempts == 0
    assert job.next_attempt_at == expected_delivery
    assert not mail.outbox

    assert deliver_notifications(now=job.next_attempt_at) == 1
    assert len(mail.outbox) == 1


def test_policy_validates_quiet_hour_pair_and_timezone() -> None:
    with pytest.raises(ValidationError, match="both be set"):
        NotificationPolicy(quiet_hours_start=time(22, 0)).full_clean()
    with pytest.raises(ValidationError, match="valid IANA"):
        NotificationPolicy(timezone_name="Not/AZone").full_clean()


def test_late_lifecycle_worker_catches_up_release_expiry_and_archive(
    orchestration_data: dict[str, Any],
) -> None:
    message = _botd(orchestration_data)
    version = message.current_version
    assert process_due_lifecycle(now=version.release_at + timedelta(minutes=1)) >= 1
    message.refresh_from_db()
    assert message.status == Message.Status.EFFECTIVE
    assert process_due_lifecycle(now=version.expiry_at + timedelta(minutes=1)) >= 2
    message.refresh_from_db()
    assert message.status == Message.Status.ARCHIVED
    assert (
        LifecycleJob.objects.get(message=message, transition=LifecycleJob.Transition.EXPIRE).status
        == LifecycleJob.Status.COMPLETED
    )
    retention = LifecycleJob.objects.get(
        message=message, transition=LifecycleJob.Transition.RETENTION_REVIEW
    )
    assert process_due_lifecycle(now=retention.due_at) == 1
    assert AuditEvent.objects.filter(action="message.retention_review_due").exists()


def test_duplicate_lifecycle_execution_is_idempotent(
    orchestration_data: dict[str, Any],
) -> None:
    message = _botd(orchestration_data, "IDEMPOTENT-BOTD")
    due = message.current_version.release_at
    assert process_due_lifecycle(now=due) == 1
    lock_version = Message.objects.get(pk=message.pk).lock_version
    assert process_due_lifecycle(now=due) == 0
    assert Message.objects.get(pk=message.pk).lock_version == lock_version


def test_unapproved_at_effective_creates_policy_alert(
    orchestration_data: dict[str, Any],
) -> None:
    policy = IdentityPolicy.load()
    policy.policy_notification_email = "policy@example.test"
    policy.save()
    message = _instruction(orchestration_data, "UNAPPROVED-INS")
    assert process_due_lifecycle(now=message.current_version.effective_at) >= 1
    alert = OutboxEvent.objects.get(topic="unapproved-effective")
    assert alert.payload["recipients"] == ["policy@example.test"]


def test_approval_reschedules_and_enqueues_approval_recipients(
    orchestration_data: dict[str, Any],
) -> None:
    identity_policy = IdentityPolicy.load()
    identity_policy.approval_notification_email = "approval@example.test"
    identity_policy.save()
    message = _instruction(orchestration_data, "APPROVAL-INS", files=True)
    approved = approve_message(
        actor=orchestration_data["actor"],
        message=message,
        expected_version=message.lock_version,
        justification="Approved for issue",
        idempotency_key=uuid.uuid4(),
    )
    assert approved.status == Message.Status.APPROVED_PENDING_RELEASE
    event = OutboxEvent.objects.get(topic="message-approved")
    assert event.payload["recipients"] == [
        "approval@example.test",
        "distribution@example.test",
    ]


def test_revision_cancels_old_schedule_and_creates_new_version_jobs(
    orchestration_data: dict[str, Any],
) -> None:
    message = _botd(orchestration_data, "RESCHEDULE-BOTD")
    old_jobs = list(LifecycleJob.objects.filter(message=message).values_list("pk", flat=True))
    version = message.current_version
    revised = revise_message(
        actor=orchestration_data["actor"],
        message=message,
        expected_version=message.lock_version,
        title="Rescheduled brief",
        summary="",
        text_content="Updated",
        release_at=version.release_at + timedelta(hours=1),
        effective_at=None,
        expiry_at=version.expiry_at + timedelta(hours=1),
        group_rights={orchestration_data["group"].pk: MessageAudienceRight.Right.ALLOWED},
        reason="Timing changed",
    )
    assert not LifecycleJob.objects.filter(
        pk__in=old_jobs, status=LifecycleJob.Status.PENDING
    ).exists()
    assert LifecycleJob.objects.filter(
        message=revised, version_number=2, status=LifecycleJob.Status.PENDING
    ).exists()


def test_outbox_failure_retries_and_dead_letters(
    orchestration_data: dict[str, Any],
) -> None:
    policy = NotificationPolicy.load()
    policy.maximum_attempts = 1
    policy.save()
    OutboxEvent.objects.create(
        topic="message-created",
        payload={"message_pk": "not-a-uuid", "recipients": ["x@example.test"]},
        deduplication_key="broken-event",
        available_at=timezone.now(),
    )
    assert process_outbox(now=timezone.now() + timedelta(seconds=1)) == 0
    event = OutboxEvent.objects.get()
    assert event.status == OutboxEvent.Status.DEAD
    assert event.last_error


def test_manual_resend_requires_permission_and_records_audit(
    orchestration_data: dict[str, Any],
) -> None:
    message = _botd(orchestration_data, "RESEND-BOTD")
    now = timezone.now()
    job = NotificationJob.objects.create(
        message=message,
        kind=NotificationJob.Kind.CREATED,
        recipients=["recipient@example.test"],
        subject="Subject",
        body="Body",
        deduplication_key="original",
        scheduled_at=now,
        next_attempt_at=now,
        status=NotificationJob.Status.DEAD,
    )
    ordinary = User.objects.create_user(username="ordinary-resender")
    with pytest.raises(PermissionDenied):
        manual_resend(actor=ordinary, job=job)
    resent = manual_resend(actor=orchestration_data["actor"], job=job, now=now)
    assert resent.kind == NotificationJob.Kind.MANUAL_RESEND
    assert resent.status == NotificationJob.Status.PENDING
    assert AuditEvent.objects.filter(action="notification.manual_resend").exists()


def test_operations_ui_is_protected_updates_policy_and_resends(
    client: Client, orchestration_data: dict[str, Any]
) -> None:
    ordinary = User.objects.create_user(username="notification-viewer")
    client.force_login(ordinary)
    assert client.get("/notifications/manage/").status_code == 403
    capability = Capability.objects.create(codename=MANAGE_MESSAGES, name="Manage messages")
    ordinary.direct_capabilities.add(capability)

    response = client.post(
        "/notifications/manage/",
        {
            "creation_anchor": NotificationPolicy.Anchor.NOW,
            "creation_offset_minutes": 10,
            "approval_anchor": NotificationPolicy.Anchor.EFFECTIVE,
            "approval_offset_minutes": -30,
            "timezone_name": "Europe/London",
            "maximum_attempts": 3,
            "retry_delay_minutes": 2,
            "archive_retention_days": 180,
        },
    )
    assert response.status_code == 302
    assert NotificationPolicy.load().creation_offset_minutes == 10

    message = _botd(orchestration_data, "UI-RESEND")
    now = timezone.now()
    job = NotificationJob.objects.create(
        message=message,
        kind=NotificationJob.Kind.CREATED,
        recipients=["recipient@example.test"],
        subject="Subject",
        body="Body",
        deduplication_key="ui-original",
        scheduled_at=now,
        next_attempt_at=now,
        status=NotificationJob.Status.DEAD,
    )
    resend = client.post(f"/notifications/manage/{job.pk}/resend/")
    assert resend.status_code == 302
    assert NotificationJob.objects.filter(kind=NotificationJob.Kind.MANUAL_RESEND).exists()


def test_celery_entry_points_delegate_to_database_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("firstbrief.notifications.tasks.process_outbox", lambda: 1)
    monkeypatch.setattr("firstbrief.notifications.tasks.process_due_lifecycle", lambda: 2)
    monkeypatch.setattr("firstbrief.notifications.tasks.deliver_notifications", lambda: 3)
    assert process_outbox_task() == 1
    assert process_lifecycle_task() == 2
    assert deliver_notifications_task() == 3


def test_delivery_uses_independent_release_anchor_and_quiet_hours(
    orchestration_data: dict[str, Any],
) -> None:
    policy = NotificationPolicy.load()
    policy.creation_anchor = NotificationPolicy.Anchor.RELEASE
    policy.creation_offset_minutes = -30
    policy.quiet_hours_start = None
    policy.quiet_hours_end = None
    policy.save()
    message = _instruction(orchestration_data, "ANCHORED-INS")
    event = OutboxEvent.objects.get(topic="message-created")
    assert event.available_at == message.current_version.release_at - timedelta(minutes=30)
