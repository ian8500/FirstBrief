from __future__ import annotations

import hashlib
import io
import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.utils import timezone
from pypdf import PdfWriter

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.models import (
    MessageGroup,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Site,
)
from firstbrief.identity.models import Capability, User
from firstbrief.identity.services import APPROVE_MESSAGES, CREATE_MESSAGES, MANAGE_MESSAGES
from firstbrief.messaging.files import attach_message_pdfs, store_scanned_pdf
from firstbrief.messaging.models import (
    Approval,
    FileAsset,
    LifecycleCommand,
    Message,
    MessageAudienceRight,
    MessagePolicy,
    MessageStatusHistory,
    MessageVersion,
)
from firstbrief.messaging.scanning import ScanResult
from firstbrief.messaging.services import (
    StaleMessageError,
    approve_message,
    archive_message,
    cancel_message,
    create_message,
    expire_message,
    make_effective,
    release_message,
    require_message_access,
    resolve_audience,
    restore_message,
    revise_message,
    supersede_message,
    unapprove_message,
    withdraw_message,
)

pytestmark = pytest.mark.django_db


class CleanScanner:
    def scan(self, path: Any) -> ScanResult:
        return ScanResult(True, "clean")


class InfectedScanner:
    def scan(self, path: Any) -> ScanResult:
        return ScanResult(False, "test signature detected")


@pytest.fixture
def messaging_data() -> dict[str, Any]:
    site = Site.objects.create(code="central", name="Central")
    pmg = PrimaryMessageGroup.objects.create(code="central-pmg", name="Central PMG", site=site)
    group = MessageGroup.objects.create(code="ops", name="Operations", primary_group=pmg)
    prohibited_group = MessageGroup.objects.create(
        code="restricted", name="Restricted", primary_group=pmg
    )
    other_site = Site.objects.create(code="remote", name="Remote")
    other_pmg = PrimaryMessageGroup.objects.create(
        code="remote-pmg", name="Remote PMG", site=other_site
    )
    other_group = MessageGroup.objects.create(
        code="remote-ops", name="Remote Operations", primary_group=other_pmg
    )
    botd_type = MessageType.objects.create(
        code="botd",
        name="Brief of the Day",
        default_content_type=MessageType.ContentType.TEXT,
    )
    instruction_type = MessageType.objects.create(
        code="instruction",
        name="Instruction",
        default_content_type=MessageType.ContentType.PDF,
        requires_approval=True,
        has_subtypes=True,
        has_effective_date=True,
    )
    subtype = MessageSubType.objects.create(
        code="general",
        name="General",
        message_type=instruction_type,
        primary_group=pmg,
        minimum_validity_days=1,
        maximum_validity_days=3,
    )
    other_subtype = MessageSubType.objects.create(
        code="remote",
        name="Remote",
        message_type=instruction_type,
        primary_group=other_pmg,
        minimum_validity_days=1,
        maximum_validity_days=3,
    )
    actor = User.objects.create_superuser(username="message-admin", password="Safe-test-42!")
    return {
        "site": site,
        "pmg": pmg,
        "group": group,
        "prohibited_group": prohibited_group,
        "other_group": other_group,
        "botd_type": botd_type,
        "instruction_type": instruction_type,
        "subtype": subtype,
        "other_subtype": other_subtype,
        "actor": actor,
    }


def make_pdf(name: str) -> SimpleUploadedFile:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(output)
    return SimpleUploadedFile(name, output.getvalue(), content_type="application/pdf")


def create_botd(data: dict[str, Any], message_id: str = "BOTD-001") -> Message:
    now = timezone.now()
    return create_message(
        actor=data["actor"],
        message_id=message_id,
        kind=Message.Kind.BOTD,
        message_type=data["botd_type"],
        subtype=None,
        title="Daily brief",
        summary="Summary",
        text_content="Operational briefing content",
        release_at=now + timedelta(hours=1),
        effective_at=None,
        expiry_at=now + timedelta(days=1),
        archive_on_expiry=True,
        group_rights={data["group"].pk: MessageAudienceRight.Right.ALLOWED},
    )


def create_instruction(
    data: dict[str, Any],
    *,
    message_id: str = "INS-001",
    validity_days: int = 2,
    attach_files: bool = True,
) -> Message:
    now = timezone.now()
    message = create_message(
        actor=data["actor"],
        message_id=message_id,
        kind=Message.Kind.INSTRUCTION,
        message_type=data["instruction_type"],
        subtype=data["subtype"],
        title="Safety instruction",
        summary="Read before operating",
        text_content="",
        release_at=now + timedelta(hours=1),
        effective_at=now + timedelta(hours=2),
        expiry_at=now + timedelta(hours=2, days=validity_days),
        archive_on_expiry=True,
        group_rights={data["group"].pk: MessageAudienceRight.Right.MANDATORY},
    )
    if attach_files:
        attach_message_pdfs(
            version=message.current_version,
            display_upload=make_pdf(f"{message_id}-display.pdf"),
            print_upload=make_pdf(f"{message_id}-print.pdf"),
            actor=data["actor"],
            scanner=CleanScanner(),
        )
    return message


def test_create_botd_records_stable_aggregate_history_and_audit(
    messaging_data: dict[str, Any],
) -> None:
    message = create_botd(messaging_data)

    assert message.status == Message.Status.APPROVED_PENDING_RELEASE
    assert message.current_version.version_number == 1
    assert message.audience_rights.get().right == MessageAudienceRight.Right.ALLOWED
    assert MessageStatusHistory.objects.filter(message=message).count() == 1
    assert AuditEvent.objects.filter(action="message.created").exists()

    message.message_id = "CHANGED"
    with pytest.raises(ValidationError, match="immutable"):
        message.save()
    version = message.current_version
    version.title = "Changed in place"
    with pytest.raises(ValidationError, match="immutable"):
        version.save()
    with pytest.raises(ValidationError, match="preserved"):
        message.delete()
    with pytest.raises(ValidationError, match="preserved"):
        Message.objects.filter(pk=message.pk).delete()
    with pytest.raises(ValidationError, match="immutable"):
        MessageVersion.objects.filter(message=message).delete()


def test_create_enforces_dates_content_and_audience(messaging_data: dict[str, Any]) -> None:
    now = timezone.now()
    values = {
        "actor": messaging_data["actor"],
        "message_id": "INVALID",
        "kind": Message.Kind.BOTD,
        "message_type": messaging_data["botd_type"],
        "subtype": None,
        "title": "Invalid",
        "summary": "",
        "text_content": "",
        "release_at": now + timedelta(hours=1),
        "effective_at": None,
        "expiry_at": now + timedelta(hours=2),
        "archive_on_expiry": True,
        "group_rights": {messaging_data["group"].pk: MessageAudienceRight.Right.ALLOWED},
    }
    with pytest.raises(ValidationError, match="Text content"):
        create_message(**values)

    values["text_content"] = "Valid"
    values["release_at"] = now - timedelta(minutes=1)
    with pytest.raises(ValidationError, match="future"):
        create_message(**values)

    values["release_at"] = now + timedelta(hours=1)
    values["message_id"] = "INVALID-RIGHTS"
    values["group_rights"] = {
        messaging_data["group"].pk: MessageAudienceRight.Right.PROHIBITED
    }
    with pytest.raises(ValidationError, match="Allowed or Mandatory"):
        create_message(**values)


def test_subtype_must_match_selected_primary_message_group(
    messaging_data: dict[str, Any],
) -> None:
    now = timezone.now()
    with pytest.raises(ValidationError, match="selected Primary Message Group"):
        create_message(
            actor=messaging_data["actor"],
            message_id="INS-WRONG-PMG",
            kind=Message.Kind.INSTRUCTION,
            message_type=messaging_data["instruction_type"],
            subtype=messaging_data["other_subtype"],
            title="Wrong PMG",
            summary="",
            text_content="",
            release_at=now + timedelta(hours=1),
            effective_at=now + timedelta(hours=2),
            expiry_at=now + timedelta(days=2),
            archive_on_expiry=True,
            group_rights={
                messaging_data["group"].pk: MessageAudienceRight.Right.ALLOWED
            },
        )


def test_instruction_requires_clean_display_and_print_pdfs_before_approval(
    messaging_data: dict[str, Any],
) -> None:
    message = create_instruction(messaging_data, attach_files=False)
    with pytest.raises(ValidationError, match="Display and Print"):
        approve_message(
            actor=messaging_data["actor"],
            message=message,
            expected_version=message.lock_version,
            justification="Reviewed",
            idempotency_key=uuid.uuid4(),
        )


def test_approval_records_justification_and_requires_subtype_bound_reason(
    messaging_data: dict[str, Any],
) -> None:
    message = create_instruction(messaging_data, validity_days=6)
    with pytest.raises(ValidationError, match="outside subtype bounds"):
        approve_message(
            actor=messaging_data["actor"],
            message=message,
            expected_version=message.lock_version,
            justification="Technically reviewed",
            idempotency_key=uuid.uuid4(),
        )

    approved = approve_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        justification="Technically reviewed",
        validity_justification="Extended validity approved by operations.",
        idempotency_key=uuid.uuid4(),
    )
    approval = Approval.objects.get(message=message)
    assert approved.status == Message.Status.APPROVED_PENDING_RELEASE
    assert approval.justification == "Technically reviewed"
    assert approval.validity_justification.startswith("Extended validity")


def test_approval_adjusts_overdue_draft_release_without_detaching_files(
    messaging_data: dict[str, Any],
) -> None:
    message = create_instruction(messaging_data)
    original = message.current_version
    past = timezone.now() - timedelta(minutes=5)
    MessageVersion.objects.filter(pk=original.pk).update(release_at=past)
    original.refresh_from_db()
    key = uuid.uuid4()
    approved = approve_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        justification="Late approval",
        idempotency_key=key,
    )
    assert approved.current_version.release_at >= past
    assert approved.current_version.files.count() == 2
    repeated = approve_message(
        actor=messaging_data["actor"],
        message=approved,
        expected_version=1,
        justification="Late approval",
        idempotency_key=key,
    )
    assert repeated.status == Message.Status.APPROVED_PENDING_RELEASE
    assert Approval.objects.filter(message=message).count() == 1


def test_assigned_approver_is_enforced(messaging_data: dict[str, Any]) -> None:
    message = create_instruction(messaging_data)
    capability = Capability.objects.create(
        codename=APPROVE_MESSAGES, name="Approve messages"
    )
    assigned = User.objects.create_user(username="assigned", password="Safe-test-42!")
    outsider = User.objects.create_user(username="outsider", password="Safe-test-42!")
    assigned.direct_capabilities.add(capability)
    outsider.direct_capabilities.add(capability)
    message.approvers.add(assigned)

    with pytest.raises(PermissionDenied, match="assigned approver"):
        approve_message(
            actor=outsider,
            message=message,
            expected_version=message.lock_version,
            justification="Reviewed",
            idempotency_key=uuid.uuid4(),
        )


def test_optimistic_locking_and_command_idempotency(messaging_data: dict[str, Any]) -> None:
    message = create_botd(messaging_data)
    key = uuid.uuid4()
    withdrawn = withdraw_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        reason="Operational change",
        idempotency_key=key,
    )
    repeated = withdraw_message(
        actor=messaging_data["actor"],
        message=withdrawn,
        expected_version=1,
        reason="Operational change",
        idempotency_key=key,
    )
    assert repeated.status == Message.Status.WITHDRAWN
    assert LifecycleCommand.objects.filter(message=message).count() == 1

    with pytest.raises(ValidationError, match="another command"):
        archive_message(
            actor=messaging_data["actor"],
            message=repeated,
            expected_version=repeated.lock_version,
            idempotency_key=key,
        )
    with pytest.raises(StaleMessageError):
        revise_message(
            actor=messaging_data["actor"],
            message=repeated,
            expected_version=1,
            title="Stale",
            summary="",
            text_content="Stale",
            release_at=repeated.current_version.release_at,
            effective_at=None,
            expiry_at=repeated.current_version.expiry_at,
            group_rights={
                messaging_data["group"].pk: MessageAudienceRight.Right.ALLOWED
            },
            reason="Stale edit",
        )


def test_full_instruction_lifecycle_and_record_preservation(
    messaging_data: dict[str, Any],
) -> None:
    message = create_instruction(messaging_data)
    message = approve_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        justification="Approved",
        idempotency_key=uuid.uuid4(),
    )
    version = message.current_version
    message = release_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        idempotency_key=uuid.uuid4(),
        at=version.release_at,
    )
    assert message.status == Message.Status.RELEASED_PENDING_EFFECTIVE
    message = make_effective(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        idempotency_key=uuid.uuid4(),
        at=version.effective_at,
    )
    assert message.status == Message.Status.EFFECTIVE
    message = expire_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        idempotency_key=uuid.uuid4(),
        at=version.expiry_at,
    )
    message = archive_message(
        actor=messaging_data["actor"],
        message=message,
        expected_version=message.lock_version,
        idempotency_key=uuid.uuid4(),
    )
    assert message.status == Message.Status.ARCHIVED
    assert Message.objects.filter(pk=message.pk).exists()
    assert list(message.status_history.values_list("to_status", flat=True)) == [
        Message.Status.DRAFT,
        Message.Status.APPROVED_PENDING_RELEASE,
        Message.Status.RELEASED_PENDING_EFFECTIVE,
        Message.Status.EFFECTIVE,
        Message.Status.EXPIRED,
        Message.Status.ARCHIVED,
    ]


def test_unapprove_withdraw_cancel_and_restore_transitions(
    messaging_data: dict[str, Any],
) -> None:
    draft = create_instruction(messaging_data, message_id="INS-UNAPPROVE")
    approved = approve_message(
        actor=messaging_data["actor"],
        message=draft,
        expected_version=draft.lock_version,
        justification="Approved",
        idempotency_key=uuid.uuid4(),
    )
    unapproved = unapprove_message(
        actor=messaging_data["actor"],
        message=approved,
        expected_version=approved.lock_version,
        reason="Needs correction",
        idempotency_key=uuid.uuid4(),
    )
    assert unapproved.status == Message.Status.DRAFT

    to_withdraw = create_botd(messaging_data, "BOTD-WITHDRAW")
    withdrawn = withdraw_message(
        actor=messaging_data["actor"],
        message=to_withdraw,
        expected_version=to_withdraw.lock_version,
        reason="No longer needed",
        idempotency_key=uuid.uuid4(),
    )
    assert withdrawn.status == Message.Status.WITHDRAWN

    to_cancel = create_instruction(messaging_data, message_id="INS-CANCEL")
    to_cancel = approve_message(
        actor=messaging_data["actor"],
        message=to_cancel,
        expected_version=to_cancel.lock_version,
        justification="Approved",
        idempotency_key=uuid.uuid4(),
    )
    to_cancel = release_message(
        actor=messaging_data["actor"],
        message=to_cancel,
        expected_version=to_cancel.lock_version,
        idempotency_key=uuid.uuid4(),
        at=to_cancel.current_version.release_at,
    )
    cancelled = cancel_message(
        actor=messaging_data["actor"],
        message=to_cancel,
        expected_version=to_cancel.lock_version,
        reason="Unsafe instruction",
        idempotency_key=uuid.uuid4(),
    )
    archived = archive_message(
        actor=messaging_data["actor"],
        message=cancelled,
        expected_version=cancelled.lock_version,
        idempotency_key=uuid.uuid4(),
    )
    restored = restore_message(
        actor=messaging_data["actor"],
        message=archived,
        expected_version=archived.lock_version,
        future_expiry_at=timezone.now() + timedelta(days=10),
        reason="Reinstated by operations",
        idempotency_key=uuid.uuid4(),
    )
    assert restored.status == Message.Status.EFFECTIVE
    assert restored.current_version_number == 2
    repeated = restore_message(
        actor=messaging_data["actor"],
        message=restored,
        expected_version=1,
        future_expiry_at=None,
        reason="Reinstated by operations",
        idempotency_key=restored.commands.get(command="restored").idempotency_key,
    )
    assert repeated.current_version_number == 2


def test_supersession_links_without_replacing_original(messaging_data: dict[str, Any]) -> None:
    original = create_botd(messaging_data, "BOTD-ORIGINAL")
    replacement = create_botd(messaging_data, "BOTD-REPLACEMENT")
    supersede_message(
        actor=messaging_data["actor"],
        original=original,
        replacement=replacement,
        expected_original_version=original.lock_version,
        reason="Updated operational brief",
    )
    replacement.refresh_from_db()
    original.refresh_from_db()
    assert replacement.supersedes == original
    assert original.superseded_by == replacement
    assert Message.objects.filter(pk=original.pk).exists()


def test_audience_precedence_and_access_denial(messaging_data: dict[str, Any]) -> None:
    message = create_botd(messaging_data)
    message.audience_rights.create(
        message_group=messaging_data["prohibited_group"],
        right=MessageAudienceRight.Right.PROHIBITED,
    )
    user = User.objects.create_user(username="reader", password="Safe-test-42!")
    user.message_groups.add(messaging_data["group"], messaging_data["prohibited_group"])
    assert resolve_audience(message, user) == MessageAudienceRight.Right.PROHIBITED
    with pytest.raises(PermissionDenied):
        require_message_access(message, user)


def test_secure_pdf_storage_checksum_filename_policy_and_malware_cleanup(
    messaging_data: dict[str, Any], tmp_path: Any
) -> None:
    message = create_instruction(messaging_data, attach_files=False)
    policy = MessagePolicy.load()
    policy.enforce_pdf_filename_match = True
    policy.save()
    with override_settings(MEDIA_ROOT=tmp_path):
        with pytest.raises(ValidationError, match="filename"):
            store_scanned_pdf(
                version=message.current_version,
                role=FileAsset.Role.DISPLAY,
                upload=make_pdf("wrong.pdf"),
                actor=messaging_data["actor"],
                scanner=CleanScanner(),
            )
        upload = make_pdf("INS-001.pdf")
        expected_checksum = hashlib.sha256(upload.read()).hexdigest()
        upload.seek(0)
        asset = store_scanned_pdf(
            version=message.current_version,
            role=FileAsset.Role.DISPLAY,
            upload=upload,
            actor=messaging_data["actor"],
            scanner=CleanScanner(),
        )
        assert asset.sha256 == expected_checksum
        assert asset.storage_key.startswith("quarantine/")
        assert "INS-001" not in asset.storage_key
        with pytest.raises(ValidationError, match="test signature"):
            store_scanned_pdf(
                version=message.current_version,
                role=FileAsset.Role.PRINT,
                upload=make_pdf("INS-001.pdf"),
                actor=messaging_data["actor"],
                scanner=InfectedScanner(),
            )
        assert list(tmp_path.rglob("*.pdf")) == [tmp_path / asset.storage_key]


def test_message_ui_permission_filters_and_accessible_date_inputs(
    client: Client, messaging_data: dict[str, Any]
) -> None:
    ordinary = User.objects.create_user(
        username="ordinary", password="Safe-test-42!", site=messaging_data["site"]
    )
    client.force_login(ordinary)
    assert client.get("/messages/manage/").status_code == 403

    create_capability = Capability.objects.create(
        codename=CREATE_MESSAGES, name="Create messages"
    )
    ordinary.direct_capabilities.add(create_capability)
    ordinary.message_groups.add(messaging_data["group"])
    response = client.get("/messages/manage/new/")
    assert response.status_code == 200
    assert b'type="datetime-local"' in response.content
    invalid = client.post("/messages/manage/new/", {"message_id": ""})
    assert invalid.status_code == 200
    assert b"There is a problem" in invalid.content


def test_service_permission_is_deny_by_default(messaging_data: dict[str, Any]) -> None:
    ordinary = User.objects.create_user(username="no-authority", password="Safe-test-42!")
    now = timezone.now()
    with pytest.raises(PermissionDenied):
        create_message(
            actor=ordinary,
            message_id="DENIED",
            kind=Message.Kind.BOTD,
            message_type=messaging_data["botd_type"],
            subtype=None,
            title="Denied",
            summary="",
            text_content="Denied",
            release_at=now + timedelta(hours=1),
            effective_at=None,
            expiry_at=now + timedelta(hours=2),
            archive_on_expiry=True,
            group_rights={
                messaging_data["group"].pk: MessageAudienceRight.Right.ALLOWED
            },
        )


def test_author_cannot_target_or_enumerate_another_site(
    client: Client, messaging_data: dict[str, Any]
) -> None:
    capability = Capability.objects.create(codename=CREATE_MESSAGES, name="Create messages")
    author = User.objects.create_user(
        username="site-author",
        password="Safe-test-42!",
        site=messaging_data["site"],
    )
    author.direct_capabilities.add(capability)
    now = timezone.now()
    with pytest.raises(PermissionDenied, match="your site"):
        create_message(
            actor=author,
            message_id="CROSS-SITE",
            kind=Message.Kind.BOTD,
            message_type=messaging_data["botd_type"],
            subtype=None,
            title="Cross site",
            summary="",
            text_content="Not allowed",
            release_at=now + timedelta(hours=1),
            effective_at=None,
            expiry_at=now + timedelta(hours=2),
            archive_on_expiry=True,
            group_rights={
                messaging_data["other_group"].pk: MessageAudienceRight.Right.ALLOWED
            },
        )

    client.force_login(author)
    response = client.get("/messages/manage/new/")
    assert response.status_code == 200
    assert b"Remote Operations" not in response.content
    assert b"Operations (ops)" in response.content


def test_seeded_lifecycle_capability_names_are_distinct() -> None:
    assert {CREATE_MESSAGES, APPROVE_MESSAGES, MANAGE_MESSAGES} == {
        "create-messages",
        "approve-messages",
        "manage-messages",
    }
