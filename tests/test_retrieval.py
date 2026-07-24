from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

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
    MANAGE_MESSAGES,
    SEE_ALL_PMG,
    VIEW_AUDIT_HISTORY,
)
from firstbrief.messaging.models import Message, MessageAudienceRight, MessageVersion
from firstbrief.operations.models import MessageReceipt
from firstbrief.retrieval.services import (
    message_suggestions,
    permitted_maintenance_actions,
    search_messages,
    user_suggestions,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def retrieval_data() -> dict[str, Any]:
    north = Site.objects.create(code="search-north", name="Search North")
    south = Site.objects.create(code="search-south", name="Search South")
    north_pmg = PrimaryMessageGroup.objects.create(
        code="search-north-pmg", name="North PMG", site=north
    )
    south_pmg = PrimaryMessageGroup.objects.create(
        code="search-south-pmg", name="South PMG", site=south
    )
    north_group = MessageGroup.objects.create(
        code="search-north-group", name="North Operations", primary_group=north_pmg
    )
    blocked_group = MessageGroup.objects.create(
        code="search-blocked-group", name="North Blocked", primary_group=north_pmg
    )
    south_group = MessageGroup.objects.create(
        code="search-south-group", name="South Secret", primary_group=south_pmg
    )
    message_type = MessageType.objects.create(
        code="search-instruction",
        name="Search Instruction",
        default_content_type=MessageType.ContentType.PDF,
        has_subtypes=True,
        has_effective_date=True,
    )
    north_subtype = MessageSubType.objects.create(
        code="search-north-subtype",
        name="North General",
        primary_group=north_pmg,
        message_type=message_type,
        maximum_validity_days=365,
    )
    south_subtype = MessageSubType.objects.create(
        code="search-south-subtype",
        name="South General",
        primary_group=south_pmg,
        message_type=message_type,
        maximum_validity_days=365,
    )
    role = Role.objects.create(name="Search reader")
    role.message_types.add(message_type)
    originator = User.objects.create_superuser(
        username="search-originator",
        password="Safe-test-42!",
        email="originator@example.test",
    )
    reader = User.objects.create_user(
        username="north-reader",
        first_name="Nora",
        last_name="Reader",
        password="Safe-test-42!",
        site=north,
    )
    reader.roles.add(role)
    reader.message_groups.add(north_group, blocked_group)
    authority = User.objects.create_user(
        username="north-authority",
        first_name="Ada",
        last_name="Authority",
        password="Safe-test-42!",
        site=north,
    )
    authority.roles.add(role)
    authority.message_groups.add(north_group)
    south_user = User.objects.create_user(
        username="south-secret-user",
        first_name="Sally",
        last_name="Secret",
        password="Safe-test-42!",
        site=south,
    )
    south_user.roles.add(role)
    south_user.message_groups.add(south_group)
    capabilities = {
        code: Capability.objects.create(codename=code, name=code.replace("-", " ").title())
        for code in (APPROVE_MESSAGES, MANAGE_MESSAGES, SEE_ALL_PMG, VIEW_AUDIT_HISTORY)
    }
    authority.direct_capabilities.add(
        capabilities[APPROVE_MESSAGES],
        capabilities[MANAGE_MESSAGES],
    )
    return {
        "north": north,
        "south": south,
        "north_group": north_group,
        "blocked_group": blocked_group,
        "south_group": south_group,
        "message_type": message_type,
        "north_subtype": north_subtype,
        "south_subtype": south_subtype,
        "originator": originator,
        "reader": reader,
        "authority": authority,
        "south_user": south_user,
        "capabilities": capabilities,
    }


def create_search_message(
    data: dict[str, Any],
    message_id: str,
    *,
    group: MessageGroup | None = None,
    subtype: MessageSubType | None = None,
    status: str = Message.Status.EFFECTIVE,
    title: str = "Operational search title",
    summary: str = "Searchable summary",
    content: str = "Display content phrase",
    release_delta: timedelta = timedelta(days=-2),
    effective_delta: timedelta = timedelta(days=-1),
    expiry_delta: timedelta = timedelta(days=5),
) -> Message:
    message = Message.objects.create(
        message_id=message_id,
        kind=Message.Kind.INSTRUCTION,
        message_type=data["message_type"],
        subtype=subtype or data["north_subtype"],
        originator=data["originator"],
        status=status,
    )
    now = timezone.now()
    MessageVersion.objects.create(
        message=message,
        version_number=1,
        title=title,
        summary=summary,
        searchable_content=content,
        release_at=now + release_delta,
        effective_at=now + effective_delta,
        expiry_at=now + expiry_delta,
        created_by=data["originator"],
    )
    MessageAudienceRight.objects.create(
        message=message,
        message_group=group or data["north_group"],
        right=MessageAudienceRight.Right.MANDATORY,
    )
    return message


def test_combined_search_filters_read_dates_archive_and_future(
    retrieval_data: dict[str, Any],
) -> None:
    match = create_search_message(
        retrieval_data,
        "NORTH-SEARCH-001",
        title="Emergency Procedure",
        summary="Hydraulic response",
        content="isolate the blue valve",
    )
    MessageReceipt.objects.create(
        user=retrieval_data["reader"],
        message=match,
        first_read_at=timezone.now(),
    )
    create_search_message(retrieval_data, "NORTH-OTHER-002", title="Routine note")
    archived = create_search_message(
        retrieval_data,
        "NORTH-ARCHIVE-003",
        status=Message.Status.ARCHIVED,
    )
    future = create_search_message(
        retrieval_data,
        "NORTH-FUTURE-004",
        status=Message.Status.RELEASED_PENDING_EFFECTIVE,
        release_delta=timedelta(hours=-1),
        effective_delta=timedelta(days=1),
    )
    now = timezone.localdate()
    results = search_messages(
        retrieval_data["reader"],
        {
            "message_id": "SEARCH",
            "title": "Emergency",
            "summary": "Hydraulic",
            "content": "blue valve",
            "group": str(retrieval_data["north_group"].pk),
            "subtype": str(retrieval_data["north_subtype"].pk),
            "read_status": "read",
            "release_from": now - timedelta(days=3),
            "release_to": now,
            "effective_from": now - timedelta(days=2),
            "effective_to": now,
            "expiry_from": now,
            "expiry_to": now + timedelta(days=6),
            "sort": "title",
            "direction": "asc",
        },
    )
    assert list(results.values_list("pk", flat=True)) == [match.pk]
    default_ids = set(
        search_messages(retrieval_data["reader"], {}).values_list("message_id", flat=True)
    )
    assert archived.message_id not in default_ids
    assert future.message_id not in default_ids
    included = set(
        search_messages(
            retrieval_data["reader"],
            {"include_archived": True, "include_future": True},
        ).values_list("message_id", flat=True)
    )
    assert {archived.message_id, future.message_id} <= included


def test_scope_cannot_leak_through_counts_suggestions_or_export(
    client: Client,
    retrieval_data: dict[str, Any],
) -> None:
    visible = create_search_message(retrieval_data, "NORTH-VISIBLE", title="=FORMULA()")
    prohibited = create_search_message(
        retrieval_data,
        "NORTH-PROHIBITED",
        group=retrieval_data["blocked_group"],
    )
    MessageAudienceRight.objects.create(
        message=prohibited,
        message_group=retrieval_data["north_group"],
        right=MessageAudienceRight.Right.PROHIBITED,
    )
    south = create_search_message(
        retrieval_data,
        "SOUTH-SECRET",
        group=retrieval_data["south_group"],
        subtype=retrieval_data["south_subtype"],
        title="Classified southern title",
    )
    client.force_login(retrieval_data["reader"])
    page = client.get("/search/?include_archived=on&include_future=on")
    body = page.content.decode()
    assert page.context["page"].paginator.count == 1
    assert visible.message_id in body
    assert prohibited.message_id not in body
    assert south.message_id not in body
    suggestions = client.get("/search/suggest/messages/?q=SOU").json()["results"]
    assert suggestions == []
    exported = client.get("/search/export.csv?include_archived=on&include_future=on")
    export_body = exported.content.decode()
    assert visible.message_id in export_body
    assert prohibited.message_id not in export_body
    assert south.message_id not in export_body
    assert exported["Cache-Control"] == "private, no-store"
    assert "'=FORMULA()" in export_body
    assert AuditEvent.objects.filter(action="message.search.exported").exists()
    assert client.get(f"/search/messages/{visible.pk}/").status_code == 200
    assert client.get(f"/search/messages/{south.pk}/").status_code == 403


def test_user_and_message_suggestions_require_three_characters_and_format(
    retrieval_data: dict[str, Any],
) -> None:
    create_search_message(retrieval_data, "NOR-001", title="Northern instruction")
    assert user_suggestions(retrieval_data["reader"], "No") == []
    assert message_suggestions(retrieval_data["reader"], "NO") == []
    north_suggestions = user_suggestions(retrieval_data["reader"], "Nor")
    assert {"value": "north-reader", "label": "Nora, Reader (north-reader)"} in north_suggestions
    assert message_suggestions(retrieval_data["reader"], "NOR") == [
        {"value": "NOR-001", "label": "NOR-001 — Northern instruction"}
    ]
    assert user_suggestions(retrieval_data["reader"], "Sal") == []


def test_search_pagination_is_stable_and_query_count_is_bounded(
    client: Client,
    retrieval_data: dict[str, Any],
) -> None:
    for number in range(31):
        create_search_message(retrieval_data, f"NORTH-PAGE-{number:02d}")
    client.force_login(retrieval_data["reader"])
    with CaptureQueriesContext(connection) as captured:
        first = client.get("/search/?sort=message_id&direction=asc")
    second = client.get("/search/?sort=message_id&direction=asc&page=2")
    first_ids = [row.message.message_id for row in first.context["rows"]]
    second_ids = [row.message.message_id for row in second.context["rows"]]
    assert first_ids == sorted(first_ids)
    assert second_ids == sorted(second_ids)
    assert set(first_ids).isdisjoint(second_ids)
    assert len(captured) <= 12


def test_maintenance_grid_actions_filters_scope_and_audit_permission(
    client: Client,
    retrieval_data: dict[str, Any],
) -> None:
    draft = create_search_message(
        retrieval_data,
        "NORTH-DRAFT",
        status=Message.Status.DRAFT,
    )
    archived = create_search_message(
        retrieval_data,
        "NORTH-ARCHIVED",
        status=Message.Status.ARCHIVED,
    )
    south = create_search_message(
        retrieval_data,
        "SOUTH-MAINTENANCE",
        group=retrieval_data["south_group"],
        subtype=retrieval_data["south_subtype"],
    )
    AuditEvent.objects.create(
        actor=retrieval_data["originator"],
        action="message.revised",
        object_type="Message",
        object_id=str(draft.pk),
    )
    authority = retrieval_data["authority"]
    assert permitted_maintenance_actions(authority, draft) == ("edit", "approve")
    assert permitted_maintenance_actions(authority, archived) == ("edit", "restore")
    client.force_login(authority)
    grid = client.get(f"/messages/manage/?status={Message.Status.DRAFT}")
    body = grid.content.decode()
    assert draft.message_id in body
    assert archived.message_id not in body
    assert south.message_id not in body
    detail = client.get(f"/messages/manage/{draft.pk}/")
    assert "Audit history" not in detail.content.decode()
    authority.direct_capabilities.add(retrieval_data["capabilities"][VIEW_AUDIT_HISTORY])
    detail = client.get(f"/messages/manage/{draft.pk}/")
    assert "Audit history" in detail.content.decode()
    assert "message.revised" in detail.content.decode()
    authority.direct_capabilities.add(retrieval_data["capabilities"][SEE_ALL_PMG])
    grid = client.get("/messages/manage/")
    assert south.message_id in grid.content.decode()
