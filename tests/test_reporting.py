from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.models import (
    MessageGroup,
    MessageType,
    PrimaryMessageGroup,
    Sector,
    Site,
)
from firstbrief.identity.models import Capability, Role, SupervisorRelationship, User
from firstbrief.identity.services import VIEW_REPORTS
from firstbrief.messaging.models import Message, MessageAudienceRight, MessageVersion
from firstbrief.operations.models import MessageAccessEvent, MessageReceipt
from firstbrief.reporting.catalogue import REPORTS
from firstbrief.reporting.models import ImportChangeRecord, ReportingCohort
from firstbrief.reporting.services import build_report, create_report_run, execute_queued_report

pytestmark = pytest.mark.django_db


@pytest.fixture
def report_data() -> dict[str, Any]:
    north = Site.objects.create(code="report-north", name="Report North")
    south = Site.objects.create(code="report-south", name="Report South")
    pmg = PrimaryMessageGroup.objects.create(code="report-pmg", name="Report PMG", site=north)
    south_pmg = PrimaryMessageGroup.objects.create(
        code="report-south-pmg", name="South PMG", site=south
    )
    group = MessageGroup.objects.create(
        code="report-ops", name="Report Operations", primary_group=pmg
    )
    blocked = MessageGroup.objects.create(code="report-blocked", name="Blocked", primary_group=pmg)
    south_group = MessageGroup.objects.create(
        code="report-south-group", name="South Group", primary_group=south_pmg
    )
    sector = Sector.objects.create(
        code="report-sector", name="Report Sector", identification="RS", primary_group=pmg
    )
    sector.message_groups.add(group)
    message_type = MessageType.objects.create(
        code="report-text",
        name="Report text",
        default_content_type=MessageType.ContentType.TEXT,
    )
    role = Role.objects.create(name="Report reader")
    role.message_types.add(message_type)
    capability = Capability.objects.create(codename=VIEW_REPORTS, name="View reports")
    actor = User.objects.create_user(
        username="report-manager", password="Safe-test-42!", site=north
    )
    actor.roles.add(role)
    actor.message_groups.add(group)
    actor.direct_capabilities.add(capability)
    reader = User.objects.create_user(
        username="report-reader",
        first_name="Rita",
        last_name="Reader",
        password="Safe-test-42!",
        site=north,
    )
    reader.roles.add(role)
    reader.message_groups.add(group)
    excluded = User.objects.create_user(
        username="report-excluded",
        password="Safe-test-42!",
        site=north,
        include_in_reports=False,
    )
    excluded.roles.add(role)
    excluded.message_groups.add(group)
    south_user = User.objects.create_user(
        username="report-south-user", password="Safe-test-42!", site=south
    )
    south_user.roles.add(role)
    south_user.message_groups.add(south_group)
    cohort = ReportingCohort.objects.create(
        code="report-users",
        name="Report users",
        kind=ReportingCohort.Kind.USER_GROUP,
        site=north,
    )
    cohort.members.add(reader)
    watch = ReportingCohort.objects.create(
        code="report-watch",
        name="Report watch",
        kind=ReportingCohort.Kind.WATCH_GROUP,
        site=north,
    )
    watch.members.add(actor)
    now = timezone.now()
    message = Message.objects.create(
        message_id="REPORT-001",
        kind=Message.Kind.BOTD,
        message_type=message_type,
        originator=actor,
        status=Message.Status.EFFECTIVE,
    )
    MessageVersion.objects.create(
        message=message,
        version_number=1,
        title="=Reconciliation title",
        summary="Reporting summary",
        text_content="Report body",
        release_at=now - timedelta(days=2),
        expiry_at=now + timedelta(days=10),
        created_by=actor,
    )
    MessageAudienceRight.objects.create(
        message=message,
        message_group=group,
        right=MessageAudienceRight.Right.MANDATORY,
    )
    MessageAudienceRight.objects.create(
        message=message,
        message_group=blocked,
        right=MessageAudienceRight.Right.PROHIBITED,
    )
    MessageReceipt.objects.create(
        user=actor,
        message=message,
        first_read_at=now,
        last_accessed_at=now,
        cumulative_view_seconds=17,
        printed_at=now,
    )
    MessageAccessEvent.objects.create(
        user=actor, message=message, event_type=MessageAccessEvent.EventType.OPENED
    )
    AuditEvent.objects.create(
        actor=reader,
        action="identity.login.succeeded",
        object_type="identity.user",
        object_id=str(reader.pk),
    )
    ImportChangeRecord.objects.create(
        batch_reference="BATCH-1",
        site=north,
        change_type="update",
        object_type="user",
        object_id=str(reader.pk),
        summary="=CMD()",
        occurred_at=now,
    )
    SupervisorRelationship.objects.create(
        supervisor=actor, reportee=reader, starts_at=now - timedelta(days=1)
    )
    return {
        "actor": actor,
        "reader": reader,
        "excluded": excluded,
        "south_user": south_user,
        "group": group,
        "sector": sector,
        "cohort": cohort,
        "watch": watch,
        "message": message,
        "now": now,
    }


def test_seeded_catalogue_reconciles_all_fourteen_reports(report_data: dict[str, Any]) -> None:
    criteria = {
        "message_group": str(report_data["group"].pk),
        "sector": str(report_data["sector"].pk),
        "cohort": str(report_data["cohort"].pk),
        "user": str(report_data["reader"].pk),
        "message": str(report_data["message"].pk),
        "batch_reference": "BATCH-1",
    }
    results = {
        definition.code: build_report(report_data["actor"], definition.code, criteria)
        for definition in REPORTS
    }
    assert len(results) == 14
    assert any(row[0] == "report-reader" for row in results["F01"].rows)
    assert all(row[0] != "report-excluded" for row in results["F02"].rows)
    assert [row[0] for row in results["F03"].rows] == ["report-reader"]
    assert results["F04"].rows == []
    assert results["F05"].rows[0][0] == "report-sector"
    assert any(row[0] == "report-reader" for row in results["F06"].rows)
    assert any(row[2] == "REPORT-001" for row in results["F07"].rows)
    assert results["F08"].rows == []
    assert any("Report reader" in row[2] for row in results["F09"].rows)
    assert ["Title", "=Reconciliation title"] in results["F10"].rows
    assert results["F11"].rows[0][0] == "BATCH-1"
    assert any(row[2] == "HAVE NOT" for row in results["F12"].rows)
    assert any(row[2] == "Login" for row in results["F13"].rows)
    assert any(row[0] == "report-reader" for row in results["F14"].rows)


def test_period_filters_login_and_effective_message_activity(
    report_data: dict[str, Any],
) -> None:
    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    result = build_report(
        report_data["actor"],
        "F13",
        {
            "message_group": str(report_data["group"].pk),
            "period_from": tomorrow,
            "period_to": tomorrow,
        },
    )
    assert result.rows == []


def test_background_snapshot_exports_and_formula_protection(
    client: Client, report_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("firstbrief.reporting.tasks.generate_report.delay", lambda run_id: None)
    run = create_report_run(
        report_data["actor"],
        "F11",
        {"batch_reference": "BATCH-1"},
        force_async=True,
    )
    assert run.status == "queued"
    execute_queued_report(run)
    client.force_login(report_data["actor"])
    csv_response = client.get(f"/reports/runs/{run.pk}/report.csv")
    assert csv_response.status_code == 200
    assert b"'=CMD()" in csv_response.content
    assert csv_response["Cache-Control"] == "private, no-store"
    pdf_response = client.get(f"/reports/runs/{run.pk}/report.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content.startswith(b"%PDF")


def test_report_access_is_capability_and_owner_scoped(
    client: Client, report_data: dict[str, Any]
) -> None:
    run = create_report_run(report_data["actor"], "F02", {})
    client.force_login(report_data["reader"])
    assert client.get("/reports/").status_code == 403
    report_data["reader"].direct_capabilities.add(Capability.objects.get(codename=VIEW_REPORTS))
    assert client.get(f"/reports/runs/{run.pk}/").status_code == 403
