from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import DatabaseError, connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from reportlab.pdfgen import canvas

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.models import (
    MessageGroup,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Site,
)
from firstbrief.identity.models import Capability, Role, User
from firstbrief.identity.services import (
    APPROVE_MESSAGES,
    MANAGE_CONFIGURATION,
    MANAGE_MESSAGES,
)
from firstbrief.messaging.models import (
    FileAsset,
    Message,
    MessageAudienceRight,
    MessageStatusHistory,
    MessageVersion,
)
from firstbrief.notifications.models import NotificationJob
from firstbrief.operations.models import (
    DashboardPreference,
    MessageAccessEvent,
    MessageReceipt,
    MessageViewSession,
    OperationalPolicy,
    ReadingPosition,
)
from firstbrief.operations.services import (
    accessible_message,
    accessible_messages,
    close_message_view,
    dashboard_data,
    email_message_to_self,
    message_rows,
    open_message_view,
    record_print,
    submit_feedback,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def operational_data() -> dict[str, Any]:
    north = Site.objects.create(code="ops-north", name="Operations North")
    south = Site.objects.create(code="ops-south", name="Operations South")
    north_pmg = PrimaryMessageGroup.objects.create(
        code="ops-north-pmg", name="North PMG", site=north
    )
    south_pmg = PrimaryMessageGroup.objects.create(
        code="ops-south-pmg", name="South PMG", site=south
    )
    default_group = MessageGroup.objects.create(
        code="ops-default", name="Default Group", primary_group=north_pmg
    )
    other_group = MessageGroup.objects.create(
        code="ops-other", name="Other Group", primary_group=north_pmg
    )
    south_group = MessageGroup.objects.create(
        code="ops-south-group", name="South Group", primary_group=south_pmg
    )
    message_type = MessageType.objects.create(
        code="ops-brief",
        name="Operational Brief",
        default_content_type=MessageType.ContentType.TEXT,
        has_subtypes=True,
    )
    subtype = MessageSubType.objects.create(
        code="ops-general",
        name="General",
        primary_group=north_pmg,
        message_type=message_type,
        maximum_validity_days=365,
    )
    role = Role.objects.create(name="Operational reader")
    role.message_types.add(message_type)
    originator = User.objects.create_superuser(
        username="ops-originator",
        password="Safe-test-42!",
        email="originator@example.test",
    )
    reader = User.objects.create_user(
        username="ops-reader",
        password="Safe-test-42!",
        email="reader@example.test",
        site=north,
        default_message_group=default_group,
    )
    reader.roles.add(role)
    reader.message_groups.add(default_group, other_group)
    outsider = User.objects.create_user(
        username="ops-outsider",
        password="Safe-test-42!",
        email="outsider@example.test",
        site=south,
    )
    outsider.roles.add(role)
    outsider.message_groups.add(south_group)
    return {
        "north": north,
        "south": south,
        "default_group": default_group,
        "other_group": other_group,
        "south_group": south_group,
        "message_type": message_type,
        "subtype": subtype,
        "role": role,
        "originator": originator,
        "reader": reader,
        "outsider": outsider,
    }


def create_operational_message(
    data: dict[str, Any],
    message_id: str,
    *,
    right: str = MessageAudienceRight.Right.MANDATORY,
    group: MessageGroup | None = None,
    status: str = Message.Status.EFFECTIVE,
    effective_delta: timedelta = timedelta(hours=-1),
    kind: str = Message.Kind.INSTRUCTION,
) -> Message:
    now = timezone.now()
    message = Message.objects.create(
        message_id=message_id,
        kind=kind,
        message_type=data["message_type"],
        subtype=data["subtype"],
        originator=data["originator"],
        status=status,
    )
    MessageVersion.objects.create(
        message=message,
        version_number=1,
        title=f"Title for {message_id}",
        summary=f"Summary for {message_id}",
        text_content=f"Content for {message_id}",
        release_at=now - timedelta(hours=2),
        effective_at=now + effective_delta,
        expiry_at=now + timedelta(days=5),
        created_by=data["originator"],
    )
    MessageAudienceRight.objects.create(
        message=message,
        message_group=group or data["default_group"],
        right=right,
    )
    return message


def test_access_scope_enforces_role_group_site_and_prohibited_precedence(
    operational_data: dict[str, Any],
) -> None:
    visible = create_operational_message(operational_data, "VISIBLE")
    blocked = create_operational_message(
        operational_data,
        "BLOCKED",
        group=operational_data["other_group"],
    )
    MessageAudienceRight.objects.create(
        message=blocked,
        message_group=operational_data["default_group"],
        right=MessageAudienceRight.Right.PROHIBITED,
    )
    south = create_operational_message(
        operational_data,
        "SOUTH",
        group=operational_data["south_group"],
    )

    ids = set(accessible_messages(operational_data["reader"]).values_list("message_id", flat=True))
    assert visible.message_id in ids
    assert blocked.message_id not in ids
    assert south.message_id not in ids
    with pytest.raises(PermissionDenied):
        accessible_message(operational_data["outsider"], visible.pk)


def test_dashboard_keeps_effective_since_login_regardless_of_read_state(
    operational_data: dict[str, Any],
) -> None:
    previous_login = timezone.now() - timedelta(hours=4)
    mandatory = create_operational_message(
        operational_data, "NEW-MANDATORY", effective_delta=timedelta(hours=-2)
    )
    MessageReceipt.objects.create(
        user=operational_data["reader"],
        message=mandatory,
        first_read_at=timezone.now() - timedelta(hours=1),
        cleared_at=timezone.now() - timedelta(minutes=30),
    )
    current_botd = create_operational_message(
        operational_data,
        "CURRENT-BOTD",
        right=MessageAudienceRight.Right.ALLOWED,
        kind=Message.Kind.BOTD,
    )
    create_operational_message(
        operational_data,
        "OTHER-BOTD",
        right=MessageAudienceRight.Right.ALLOWED,
        group=operational_data["other_group"],
        kind=Message.Kind.BOTD,
    )
    forthcoming = create_operational_message(
        operational_data,
        "FORTHCOMING",
        status=Message.Status.RELEASED_PENDING_EFFECTIVE,
        effective_delta=timedelta(hours=2),
    )
    create_operational_message(
        operational_data,
        "TOO-EARLY",
        status=Message.Status.RELEASED_PENDING_EFFECTIVE,
        effective_delta=timedelta(hours=48),
    )

    result = dashboard_data(operational_data["reader"], previous_login)
    assert mandatory in result["effective_since"]
    assert forthcoming in result["forthcoming"]
    assert all(message.message_id != "TOO-EARLY" for message in result["forthcoming"])
    assert current_botd in result["botd"]
    assert [message.message_id for message in result["botd"]] == ["CURRENT-BOTD"]


def test_mandatory_and_other_lists_track_unread_clear_sort_and_group(
    operational_data: dict[str, Any],
) -> None:
    mandatory = create_operational_message(operational_data, "B-MANDATORY")
    allowed = create_operational_message(
        operational_data,
        "A-OTHER",
        right=MessageAudienceRight.Right.ALLOWED,
    )
    MessageReceipt.objects.create(
        user=operational_data["reader"],
        message=mandatory,
        first_read_at=timezone.now(),
        cleared_at=timezone.now(),
    )

    mandatory_rows = message_rows(operational_data["reader"], list_kind="mandatory")
    other_rows = message_rows(operational_data["reader"], list_kind="other", sort="message")
    assert mandatory_rows == []
    assert [row.message for row in other_rows] == [allowed, mandatory]
    assert other_rows[0].unread is True
    assert other_rows[1].cleared is True


def test_view_close_accumulates_bounded_time_and_prevents_replay(
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "ACKNOWLEDGE")
    annotated = accessible_message(operational_data["reader"], message.pk)
    session = open_message_view(
        actor=operational_data["reader"],
        message=annotated,
        browser_session_key="session-1",
    )
    MessageViewSession.objects.filter(pk=session.pk).update(
        opened_at=timezone.now() - timedelta(seconds=30)
    )
    receipt = close_message_view(
        actor=operational_data["reader"],
        message=annotated,
        view_session_id=session.pk,
        active_seconds=500,
        clear=False,
    )
    assert 30 <= receipt.cumulative_view_seconds <= 35
    assert receipt.first_read_at is not None
    assert receipt.cleared_at is None
    with pytest.raises(ValidationError, match="no longer active"):
        close_message_view(
            actor=operational_data["reader"],
            message=annotated,
            view_session_id=session.pk,
            active_seconds=10,
            clear=True,
        )

    second = open_message_view(
        actor=operational_data["reader"],
        message=annotated,
        browser_session_key="session-1",
    )
    MessageViewSession.objects.filter(pk=second.pk).update(
        opened_at=timezone.now() - timedelta(seconds=12)
    )
    cleared = close_message_view(
        actor=operational_data["reader"],
        message=annotated,
        view_session_id=second.pk,
        active_seconds=10,
        clear=True,
    )
    assert cleared.cleared_at is not None
    assert cleared.cumulative_view_seconds >= 40
    assert MessageAccessEvent.objects.filter(
        event_type=MessageAccessEvent.EventType.CLEARED
    ).exists()


def test_print_email_feedback_and_audit_are_persisted(
    operational_data: dict[str, Any],
) -> None:
    message = accessible_message(
        operational_data["reader"],
        create_operational_message(operational_data, "ACTIONS").pk,
    )
    record_print(
        actor=operational_data["reader"],
        message=message,
        browser_session_key="session-actions",
    )
    email_job = email_message_to_self(
        actor=operational_data["reader"],
        message=message,
        browser_session_key="session-actions",
        secure_url="https://firstbrief.example/messages/actions/",
    )
    feedback_job = submit_feedback(
        actor=operational_data["reader"],
        message=message,
        subject="Question",
        body="Please clarify this instruction.",
        browser_session_key="session-actions",
    )
    receipt = MessageReceipt.objects.get(user=operational_data["reader"], message=message)
    assert receipt.printed_at is not None
    assert receipt.emailed_at is not None
    assert email_job.kind == NotificationJob.Kind.MESSAGE_TO_SELF
    assert feedback_job.kind == NotificationJob.Kind.FEEDBACK
    assert "reader@example.test" in email_job.recipients
    assert "originator@example.test" in feedback_job.recipients
    assert AuditEvent.objects.filter(action="message.feedback").exists()


def test_access_events_are_append_only(operational_data: dict[str, Any]) -> None:
    message = create_operational_message(operational_data, "APPEND-ONLY")
    event = MessageAccessEvent.objects.create(
        user=operational_data["reader"],
        message=message,
        event_type=MessageAccessEvent.EventType.OPENED,
    )
    event.metadata = {"changed": True}
    with pytest.raises(ValidationError, match="append-only"):
        event.save()
    with pytest.raises(ValidationError, match="append-only"):
        event.delete()
    with pytest.raises(ValidationError, match="append-only"):
        MessageAccessEvent.objects.filter(pk=event.pk).update(metadata={"changed": True})


def test_dashboard_viewer_lists_logout_and_policy_permissions(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "BROWSER-FLOW")
    User.objects.filter(pk=operational_data["reader"].pk).update(
        date_joined=timezone.now() + timedelta(days=1)
    )
    operational_data["reader"].refresh_from_db()
    client.force_login(operational_data["reader"])
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Your briefings" in dashboard.content.decode()
    assert "BROWSER-FLOW" in dashboard.content.decode()
    mandatory = client.get("/operational/mandatory/?group=subtype")
    assert mandatory.status_code == 200
    assert "General" in mandatory.content.decode()
    viewer = client.get(f"/operational/messages/{message.pk}/")
    assert viewer.status_code == 200
    assert "Acknowledge" in viewer.content.decode()
    logout = client.get("/access/logout/")
    assert "BROWSER-FLOW" in logout.content.decode()
    settings_page = client.get("/operational/settings/")
    assert settings_page.status_code == 200
    assert "Your dashboard" in settings_page.content.decode()
    denied_policy = client.post(
        "/operational/settings/",
        {
            "save_policy": "1",
            "pre_effective_hours": 48,
            "pre_effective_colour": "#123456",
            "idle_timeout_seconds": 90,
        },
    )
    assert denied_policy.status_code == 403

    preferences_response = client.post(
        "/operational/settings/",
        {
            "save_preferences": "1",
            "show_forthcoming": "on",
            "show_botd": "on",
            "show_approvals": "on",
            "show_returned_drafts": "on",
            "show_recently_opened": "on",
            "item_limit": "5",
            "expiring_within_days": "14",
        },
    )
    assert preferences_response.status_code == 302
    preference = DashboardPreference.load_for(operational_data["reader"])
    assert preference.item_limit == 5
    assert preference.expiring_within_days == 14

    capability = Capability.objects.create(
        codename=MANAGE_CONFIGURATION,
        name="Manage configuration",
    )
    operational_data["reader"].direct_capabilities.add(capability)
    settings_response = client.post(
        "/operational/settings/",
        {
            "save_policy": "1",
            "pre_effective_hours": 48,
            "pre_effective_colour": "#123456",
            "idle_timeout_seconds": 90,
        },
    )
    assert settings_response.status_code == 302
    policy = OperationalPolicy.load()
    assert policy.pre_effective_hours == 48
    assert policy.pre_effective_colour == "#123456"


def test_attention_inbox_is_role_scoped_ordered_and_explains_each_item(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    reader = operational_data["reader"]
    for codename, name in (
        (APPROVE_MESSAGES, "Approve messages"),
        (MANAGE_MESSAGES, "Manage messages"),
    ):
        reader.direct_capabilities.add(Capability.objects.create(codename=codename, name=name))

    overdue = create_operational_message(operational_data, "A-OVERDUE")
    continued = create_operational_message(operational_data, "B-CONTINUE")
    MessageReceipt.objects.create(
        user=reader,
        message=continued,
        first_read_at=timezone.now() - timedelta(minutes=10),
        last_accessed_at=timezone.now() - timedelta(minutes=5),
    )
    forthcoming = create_operational_message(
        operational_data,
        "C-FORTHCOMING",
        status=Message.Status.RELEASED_PENDING_EFFECTIVE,
        effective_delta=timedelta(hours=2),
    )
    approval = create_operational_message(
        operational_data,
        "D-APPROVAL",
        status=Message.Status.DRAFT,
    )
    approval.approvers.add(reader)
    returned = create_operational_message(
        operational_data,
        "E-RETURNED",
        status=Message.Status.DRAFT,
    )
    returned.originator = reader
    returned.save(update_fields=("originator", "updated_at"))
    MessageStatusHistory.objects.create(
        message=returned,
        from_status=Message.Status.APPROVED_PENDING_RELEASE,
        to_status=Message.Status.DRAFT,
        actor=operational_data["originator"],
        reason="Correct the operational date.",
        aggregate_version=2,
    )
    expiring = create_operational_message(
        operational_data,
        "F-EXPIRING",
        right=MessageAudienceRight.Right.ALLOWED,
    )
    failed = NotificationJob.objects.create(
        message=expiring,
        kind=NotificationJob.Kind.APPROVED,
        recipients=["ops@example.test"],
        subject="Delivery for F-EXPIRING",
        body="body",
        deduplication_key="attention-failed-visible",
        scheduled_at=timezone.now(),
        next_attempt_at=timezone.now(),
        status=NotificationJob.Status.DEAD,
    )
    hidden_message = create_operational_message(
        operational_data,
        "SOUTH-FAILED",
        group=operational_data["south_group"],
    )
    NotificationJob.objects.create(
        message=hidden_message,
        kind=NotificationJob.Kind.APPROVED,
        recipients=["south@example.test"],
        subject="Leaking subject",
        body="body",
        deduplication_key="attention-failed-hidden",
        scheduled_at=timezone.now(),
        next_attempt_at=timezone.now(),
        status=NotificationJob.Status.DEAD,
    )

    result = dashboard_data(reader, timezone.now() - timedelta(hours=4))
    items = result["attention_items"]
    references = [item.reference for item in items]
    assert overdue.message_id in references
    assert continued.message_id in references
    assert forthcoming.message_id in references
    assert approval.message_id in references
    assert returned.message_id in references
    assert failed.message.message_id in references
    assert "SOUTH-FAILED" not in references
    assert all(item.reason for item in items)
    ordering = [
        (item.urgency_rank, item.due_at, item.reference.casefold()) for item in items
    ]
    assert ordering == sorted(ordering)
    assert result["continue_item"].reference == continued.message_id

    client.force_login(reader)
    response = client.get("/")
    html = response.content.decode()
    assert 'aria-labelledby="attention-heading"' in html
    assert "Requires your attention" in html
    assert "Continue reading" in html
    assert "Correct the operational date." in html
    assert "Leaking subject" not in html
    assert "data-loading-link" in html


def test_attention_inbox_preferences_do_not_grant_or_leak_capabilities(
    operational_data: dict[str, Any],
) -> None:
    reader = operational_data["reader"]
    approval = create_operational_message(
        operational_data,
        "HIDDEN-APPROVAL",
        status=Message.Status.DRAFT,
    )
    approval.approvers.add(reader)
    failed_message = create_operational_message(
        operational_data,
        "HIDDEN-FAILURE",
        right=MessageAudienceRight.Right.ALLOWED,
    )
    NotificationJob.objects.create(
        message=failed_message,
        kind=NotificationJob.Kind.APPROVED,
        recipients=["ops@example.test"],
        subject="Hidden failed delivery",
        body="body",
        deduplication_key="attention-no-capability",
        scheduled_at=timezone.now(),
        next_attempt_at=timezone.now(),
        status=NotificationJob.Status.DEAD,
    )
    preference = DashboardPreference.load_for(reader)
    preference.show_approvals = True
    preference.show_notification_failures = True
    preference.save()

    result = dashboard_data(reader, timezone.now() - timedelta(days=1))
    keys = {item.key for item in result["attention_items"]}
    assert not any(key.startswith("approval:") for key in keys)
    assert not any(key.startswith("notification:") for key in keys)


def test_attention_query_count_does_not_grow_per_message(
    operational_data: dict[str, Any],
) -> None:
    reader = operational_data["reader"]
    OperationalPolicy.load()
    DashboardPreference.load_for(reader)
    create_operational_message(operational_data, "QUERY-ONE")
    with CaptureQueriesContext(connection) as one_context:
        dashboard_data(reader, timezone.now() - timedelta(days=1))
    for index in range(8):
        create_operational_message(operational_data, f"QUERY-{index + 2}")
    with CaptureQueriesContext(connection) as many_context:
        dashboard_data(reader, timezone.now() - timedelta(days=1))
    assert len(many_context) <= len(one_context) + 2


def test_attention_inbox_degrades_without_losing_reader_tasks(
    operational_data: dict[str, Any],
) -> None:
    reader = operational_data["reader"]
    reader.direct_capabilities.add(
        Capability.objects.create(codename=MANAGE_MESSAGES, name="Manage messages")
    )
    message = create_operational_message(operational_data, "DEGRADED-READER-TASK")
    with patch(
        "firstbrief.operations.services.NotificationJob.objects.filter",
        side_effect=DatabaseError("notification store unavailable"),
    ):
        result = dashboard_data(reader, timezone.now() - timedelta(days=1))
    assert message.message_id in {item.reference for item in result["attention_items"]}
    assert result["degraded_messages"] == [
        "Notification delivery status is temporarily unavailable. "
        "Message-reading tasks are unaffected."
    ]


def test_close_endpoint_read_then_clear_moves_between_lists(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "CLOSE-FLOW")
    client.force_login(operational_data["reader"])
    viewer = client.get(f"/operational/messages/{message.pk}/")
    view_session = viewer.context["view_session"]
    MessageViewSession.objects.filter(pk=view_session.pk).update(
        opened_at=timezone.now() - timedelta(seconds=20)
    )
    read = client.post(
        f"/operational/messages/{message.pk}/close/",
        {
            "view_session": view_session.pk,
            "active_seconds": 12,
            "action": "read",
        },
    )
    assert read.status_code == 302
    assert read["Location"] == "/operational/mandatory/"

    viewer = client.get(f"/operational/messages/{message.pk}/")
    second = viewer.context["view_session"]
    cleared = client.post(
        f"/operational/messages/{message.pk}/close/",
        {
            "view_session": second.pk,
            "active_seconds": 0,
            "action": "clear",
        },
    )
    assert cleared.status_code == 302
    assert cleared["Location"] == "/operational/other/"


def test_protected_pdf_requires_scope_and_sets_private_headers(
    client: Client,
    operational_data: dict[str, Any],
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        message = create_operational_message(operational_data, "SECURE-PDF")
        key = default_storage.save("quarantine/opaque.pdf", ContentFile(b"%PDF-1.4\n%%EOF"))
        asset = FileAsset.objects.create(
            version=message.current_version,
            role=FileAsset.Role.DISPLAY,
            original_filename="source.pdf",
            storage_key=key,
            content_type="application/pdf",
            byte_size=14,
            sha256="0" * 64,
            scan_status=FileAsset.ScanStatus.CLEAN,
            uploaded_by=operational_data["originator"],
        )
        client.force_login(operational_data["reader"])
        response = client.get(f"/operational/messages/{message.pk}/files/{asset.pk}/")
        assert response.status_code == 200
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Frame-Options"] == "SAMEORIGIN"

        client.force_login(operational_data["outsider"])
        forbidden = client.get(f"/operational/messages/{message.pk}/files/{asset.pk}/")
        assert forbidden.status_code == 403


def _searchable_pdf() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output)
    document.bookmarkPage("overview")
    document.addOutlineEntry("Overview", "overview", level=0)
    document.drawString(72, 760, "Alpha operational overview")
    document.showPage()
    document.bookmarkPage("actions")
    document.addOutlineEntry("Required actions", "actions", level=0)
    document.drawString(72, 760, "Bravo required actions")
    document.showPage()
    document.save()
    return output.getvalue()


def _attach_display_pdf(
    message: Message,
    *,
    uploader: User,
    storage_key: str,
) -> FileAsset:
    payload = _searchable_pdf()
    key = default_storage.save(storage_key, ContentFile(payload))
    return FileAsset.objects.create(
        version=message.current_version,
        role=FileAsset.Role.DISPLAY,
        original_filename="reader.pdf",
        storage_key=key,
        content_type="application/pdf",
        byte_size=len(payload),
        sha256="1" * 64,
        scan_status=FileAsset.ScanStatus.CLEAN,
        uploaded_by=uploader,
    )


def test_prohibited_message_and_pdf_are_denied(
    client: Client,
    operational_data: dict[str, Any],
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        message = create_operational_message(operational_data, "PROHIBITED-READER")
        MessageAudienceRight.objects.create(
            message=message,
            message_group=operational_data["other_group"],
            right=MessageAudienceRight.Right.PROHIBITED,
        )
        asset = _attach_display_pdf(
            message,
            uploader=operational_data["originator"],
            storage_key="quarantine/prohibited.pdf",
        )
        client.force_login(operational_data["reader"])
        assert client.get(f"/operational/messages/{message.pk}/").status_code == 403
        assert (
            client.get(f"/operational/messages/{message.pk}/files/{asset.pk}/").status_code
            == 403
        )


def test_reader_persists_page_and_exposes_protected_pdf_navigation(
    client: Client,
    operational_data: dict[str, Any],
    tmp_path: Path,
) -> None:
    with override_settings(MEDIA_ROOT=tmp_path):
        message = create_operational_message(operational_data, "POSITION-PDF")
        _attach_display_pdf(
            message,
            uploader=operational_data["originator"],
            storage_key="quarantine/position.pdf",
        )
        reader = operational_data["reader"]
        client.force_login(reader)
        response = client.get(f"/operational/messages/{message.pk}/")
        session = response.context["view_session"]
        html = response.content.decode()
        assert "Page thumbnails" in html
        assert "Required actions" in html
        assert "Search this PDF" in html
        assert 'title="Protected display PDF for POSITION-PDF, version 1"' in html
        saved = client.post(
            f"/operational/messages/{message.pk}/position/",
            {"view_session": session.pk, "page": 2, "total_pages": 2},
        )
        assert saved.status_code == 200
        assert saved.json()["progress"] == 100
        position = ReadingPosition.objects.get(user=reader, message=message)
        assert position.page == 2

        reopened = client.get(f"/operational/messages/{message.pk}/")
        assert reopened.context["last_page"] == 2
        assert "#page=2" in reopened.content.decode()


def test_reading_position_is_isolated_by_message_version(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "VERSION-POSITION")
    reader = operational_data["reader"]
    client.force_login(reader)
    first = client.get(f"/operational/messages/{message.pk}/")
    first_session = first.context["view_session"]
    saved = client.post(
        f"/operational/messages/{message.pk}/position/",
        {"view_session": first_session.pk, "page": 3, "total_pages": 4},
    )
    assert saved.status_code == 200

    original = message.current_version
    replacement = MessageVersion.objects.create(
        message=message,
        version_number=2,
        title="Revised reader version",
        summary=original.summary,
        text_content=original.text_content,
        release_at=original.release_at,
        effective_at=original.effective_at,
        expiry_at=original.expiry_at,
        created_by=operational_data["originator"],
    )
    message.current_version_number = 2
    message.save(update_fields=("current_version_number", "updated_at"))
    assert ReadingPosition.objects.filter(version=original, page=3).exists()
    assert not ReadingPosition.objects.filter(version=replacement).exists()

    second = client.get(f"/operational/messages/{message.pk}/")
    assert second.context["last_page"] == 1
    assert second.context["version"].version_number == 2


def test_cancellation_while_open_records_read_but_refuses_acknowledgement(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "CANCEL-WHILE-OPEN")
    reader = operational_data["reader"]
    client.force_login(reader)
    opened = client.get(f"/operational/messages/{message.pk}/")
    session = opened.context["view_session"]
    MessageViewSession.objects.filter(pk=session.pk).update(
        opened_at=timezone.now() - timedelta(seconds=20)
    )
    Message.objects.filter(pk=message.pk).update(status=Message.Status.CANCELLED)

    status = client.get(
        f"/operational/messages/{message.pk}/status/",
        {"view_session": session.pk},
    )
    assert status.status_code == 200
    assert status.json()["status"] == Message.Status.CANCELLED
    assert status.json()["can_clear"] is False

    closed = client.post(
        f"/operational/messages/{message.pk}/close/",
        {
            "view_session": session.pk,
            "active_seconds": 12,
            "action": "clear",
        },
        follow=True,
    )
    assert closed.status_code == 200
    receipt = MessageReceipt.objects.get(user=reader, message=message)
    assert receipt.first_read_at is not None
    assert receipt.cleared_at is None
    read_event = MessageAccessEvent.objects.get(
        user=reader,
        message=message,
        event_type=MessageAccessEvent.EventType.READ,
    )
    assert read_event.duration_seconds == 12
    assert read_event.metadata["lifecycle_changed_while_open"] is True
    assert not MessageAccessEvent.objects.filter(
        user=reader,
        message=message,
        event_type__in=(
            MessageAccessEvent.EventType.ACKNOWLEDGED,
            MessageAccessEvent.EventType.CLEARED,
        ),
    ).exists()


def test_acknowledgement_and_clear_evidence_is_version_bound_and_append_only(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "ACK-EVIDENCE")
    reader = operational_data["reader"]
    client.force_login(reader)
    opened = client.get(f"/operational/messages/{message.pk}/")
    session = opened.context["view_session"]
    MessageViewSession.objects.filter(pk=session.pk).update(
        opened_at=timezone.now() - timedelta(seconds=20)
    )
    response = client.post(
        f"/operational/messages/{message.pk}/close/",
        {
            "view_session": session.pk,
            "active_seconds": 10,
            "action": "clear",
        },
    )
    assert response.status_code == 302
    events = list(
        MessageAccessEvent.objects.filter(user=reader, message=message).order_by(
            "occurred_at", "pk"
        )
    )
    assert [event.event_type for event in events] == [
        MessageAccessEvent.EventType.OPENED,
        MessageAccessEvent.EventType.ACKNOWLEDGED,
        MessageAccessEvent.EventType.CLEARED,
    ]
    assert all(event.metadata["version_number"] == 1 for event in events)
    assert events[-1].duration_seconds == 10
    assert MessageReceipt.objects.get(user=reader, message=message).cleared_at is not None
    with pytest.raises(ValidationError, match="append-only"):
        events[1].delete()


def test_reader_keyboard_and_accessibility_contract(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    message = create_operational_message(operational_data, "ACCESSIBLE-READER")
    client.force_login(operational_data["reader"])
    response = client.get(f"/operational/messages/{message.pk}/")
    html = response.content.decode()
    assert 'data-help-dialog aria-labelledby="keyboard-help-heading"' in html
    assert 'aria-keyshortcuts="?"' in html
    assert 'aria-keyshortcuts="/"' not in html  # PDF-only control is correctly omitted.
    assert 'role="alert" tabindex="-1" hidden data-lifecycle-alert' in html
    assert 'aria-labelledby="reading-progress-heading"' in html
    script = Path("firstbrief/core/static/js/consumption.js").read_text()
    assert 'event.key === "?"' in script
    assert 'event.key === "/"' in script
    assert 'event.key === "["' in script
    assert "helpReturnFocus" in script


def test_login_preserves_previous_login_for_effective_dashboard(
    client: Client,
    operational_data: dict[str, Any],
) -> None:
    previous = timezone.now() - timedelta(days=2)
    reader = operational_data["reader"]
    reader.last_login = previous
    reader.save(update_fields=("last_login",))
    response = client.post(
        "/access/login/",
        {"username": reader.username, "password": "Safe-test-42!"},
    )
    assert response.status_code == 302
    assert client.session["previous_login_at"] == previous.isoformat()
