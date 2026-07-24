"""Authorised report datasets, snapshots and export rendering."""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from firstbrief.assurance.models import AuditEvent
from firstbrief.assurance.services import record_event
from firstbrief.configuration.models import Sector
from firstbrief.identity.models import SupervisorRelationship, User
from firstbrief.identity.services import (
    SEE_ALL_PMG,
    VIEW_REPORTS,
    has_capability,
    require_capability,
)
from firstbrief.messaging.models import Message, MessageAudienceRight
from firstbrief.operations.models import MessageAccessEvent, MessageReceipt
from firstbrief.reporting.catalogue import CATALOGUE_VERSION, REPORT_BY_CODE
from firstbrief.reporting.models import ImportChangeRecord, ReportingCohort, ReportRun
from firstbrief.retrieval.services import search_messages

MAX_SNAPSHOT_ROWS = 10_000
ASYNC_ROW_THRESHOLD = 500


@dataclass(frozen=True)
class ReportResult:
    columns: tuple[str, ...]
    rows: list[list[Any]]


def _site_timezone() -> ZoneInfo:
    return ZoneInfo(settings.SITE_TIME_ZONE)


def _display_time(value: datetime | None) -> str:
    if value is None:
        return ""
    return timezone.localtime(value, _site_timezone()).strftime("%Y-%m-%d %H:%M")


def _period(criteria: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    start = criteria.get("period_from")
    end = criteria.get("period_to")
    start_dt = (
        datetime.combine(date.fromisoformat(start), time.min, tzinfo=_site_timezone())
        if isinstance(start, str) and start
        else None
    )
    end_dt = (
        datetime.combine(date.fromisoformat(end), time.max, tzinfo=_site_timezone())
        if isinstance(end, str) and end
        else None
    )
    return start_dt, end_dt


def _within_period(queryset: QuerySet[Any], field: str, criteria: dict[str, Any]) -> QuerySet[Any]:
    start, end = _period(criteria)
    if start:
        queryset = queryset.filter(**{f"{field}__gte": start})
    if end:
        queryset = queryset.filter(**{f"{field}__lte": end})
    return queryset


def reportable_users(actor: User, criteria: dict[str, Any]) -> QuerySet[User]:
    from firstbrief.identity.services import visible_users_for

    users = visible_users_for(actor).filter(include_in_reports=True, is_active=True)
    if criteria.get("site"):
        users = users.filter(site_id=int(criteria["site"]))
    if criteria.get("primary_group"):
        users = users.filter(
            message_groups__primary_group_id=int(criteria["primary_group"])
        ).distinct()
    if criteria.get("message_group"):
        users = users.filter(message_groups__id=int(criteria["message_group"]))
    for group_id in criteria.get("associated_groups", []):
        users = users.filter(message_groups__id=int(group_id))
    if criteria.get("role"):
        users = users.filter(roles__id=int(criteria["role"]))
    return users.order_by("username", "pk").distinct()


def reportable_messages(actor: User, criteria: dict[str, Any]) -> QuerySet[Message]:
    messages = search_messages(
        actor,
        {
            "include_archived": bool(criteria.get("include_archived")),
            "include_future": bool(criteria.get("include_future")),
            "group": criteria.get("message_group"),
            "sort": "message_id",
        },
    )
    if criteria.get("primary_group"):
        messages = messages.filter(
            audience_rights__message_group__primary_group_id=int(criteria["primary_group"])
        )
    associated = criteria.get("associated_groups", [])
    if associated:
        messages = messages.filter(audience_rights__message_group_id__in=associated)
    start, end = _period(criteria)
    if start:
        messages = messages.filter(
            Q(
                versions__version_number=F("current_version_number"),
                versions__effective_at__gte=start,
            )
            | Q(
                versions__version_number=F("current_version_number"),
                versions__effective_at__isnull=True,
                versions__release_at__gte=start,
            )
        )
    if end:
        messages = messages.filter(
            Q(
                versions__version_number=F("current_version_number"),
                versions__effective_at__lte=end,
            )
            | Q(
                versions__version_number=F("current_version_number"),
                versions__effective_at__isnull=True,
                versions__release_at__lte=end,
            )
        )
    return messages.distinct()


def _right_for_user(user: User, message: Message) -> str | None:
    group_ids = set(user.message_groups.values_list("pk", flat=True))
    rights = [
        right.right
        for right in message.audience_rights.all()
        if right.message_group_id in group_ids
    ]
    if MessageAudienceRight.Right.PROHIBITED in rights:
        return None
    if MessageAudienceRight.Right.MANDATORY in rights:
        return MessageAudienceRight.Right.MANDATORY
    if MessageAudienceRight.Right.ALLOWED in rights:
        return MessageAudienceRight.Right.ALLOWED
    return None


def _selected_message(actor: User, criteria: dict[str, Any]) -> Message | None:
    message_id = criteria.get("message")
    if not message_id:
        return None
    messages = reportable_messages(
        actor, {**criteria, "include_archived": True, "include_future": True}
    )
    return messages.filter(pk=message_id).first()


def _selected_user(actor: User, criteria: dict[str, Any]) -> User | None:
    user_id = criteria.get("user")
    return reportable_users(actor, criteria).filter(pk=user_id).first() if user_id else None


def _members_result(users: QuerySet[User]) -> ReportResult:
    rows = [
        [
            user.username,
            user.first_name,
            user.last_name,
            str(user.site or ""),
            ", ".join(user.roles.values_list("name", flat=True)),
        ]
        for user in users.select_related("site").prefetch_related("roles")
    ]
    return ReportResult(("User ID", "First name", "Surname", "Site", "Roles"), rows)


def _f01(actor: User, criteria: dict[str, Any]) -> ReportResult:
    users = reportable_users(actor, criteria)
    if criteria.get("message_group"):
        users = users.filter(message_groups__id=int(criteria["message_group"]))
    return _members_result(users)


def _f02(actor: User, criteria: dict[str, Any]) -> ReportResult:
    return _members_result(reportable_users(actor, criteria))


def _cohort_members(actor: User, criteria: dict[str, Any], kind: str) -> ReportResult:
    cohort_id = criteria.get("cohort")
    if cohort_id in (None, ""):
        return _members_result(reportable_users(actor, criteria).none())
    cohorts = ReportingCohort.objects.filter(pk=int(cohort_id), kind=kind, is_active=True)
    if not (actor.is_superuser or has_capability(actor, SEE_ALL_PMG)):
        if actor.site_id is None:
            cohorts = cohorts.none()
        else:
            cohorts = cohorts.filter(site_id=actor.site_id)
    cohort = cohorts.first()
    users = reportable_users(actor, criteria)
    if cohort is None or not users.filter(reporting_cohorts=cohort).exists():
        return _members_result(users.none())
    return _members_result(users.filter(reporting_cohorts=cohort))


def _f03(actor: User, criteria: dict[str, Any]) -> ReportResult:
    return _cohort_members(actor, criteria, ReportingCohort.Kind.USER_GROUP)


def _f04(actor: User, criteria: dict[str, Any]) -> ReportResult:
    return _cohort_members(actor, criteria, ReportingCohort.Kind.WATCH_GROUP)


def _f05(actor: User, criteria: dict[str, Any]) -> ReportResult:
    sectors = Sector.objects.filter(is_active=True)
    if not (actor.is_superuser or has_capability(actor, SEE_ALL_PMG)):
        if actor.site_id is None:
            sectors = sectors.none()
        else:
            sectors = sectors.filter(primary_group__site_id=actor.site_id)
    if criteria.get("sector"):
        sectors = sectors.filter(pk=int(criteria["sector"]))
    rows: list[list[Any]] = []
    for sector in sectors.prefetch_related("message_groups", "primary_group__site"):
        for group in sector.message_groups.all():
            rows.append(
                [
                    sector.code,
                    sector.name,
                    str(sector.primary_group.site),
                    group.code,
                    group.name,
                ]
            )
    return ReportResult(("Sector ID", "Sector", "Site", "Group ID", "Message group"), rows)


def _unread_mandatory_rows(
    actor: User, criteria: dict[str, Any], users: QuerySet[User]
) -> ReportResult:
    messages = list(
        reportable_messages(actor, criteria)
        .prefetch_related("audience_rights__message_group", "versions")
        .order_by("message_id")
    )
    receipts = {
        (receipt.user_id, receipt.message_id): receipt
        for receipt in MessageReceipt.objects.filter(user__in=users, message__in=messages)
    }
    rows: list[list[Any]] = []
    for user in users.prefetch_related("message_groups"):
        for message in messages:
            if _right_for_user(user, message) != MessageAudienceRight.Right.MANDATORY:
                continue
            receipt = receipts.get((user.pk, message.pk))
            if receipt and receipt.first_read_at:
                continue
            version = message.current_version
            rows.append(
                [
                    user.username,
                    user.get_full_name(),
                    message.message_id,
                    version.title,
                    _display_time(version.effective_at or version.release_at),
                    message.get_status_display(),
                ]
            )
    return ReportResult(("User ID", "User", "Message ID", "Title", "Effective", "Status"), rows)


def _f06(actor: User, criteria: dict[str, Any]) -> ReportResult:
    return _unread_mandatory_rows(actor, criteria, reportable_users(actor, criteria))


def _f07(actor: User, criteria: dict[str, Any]) -> ReportResult:
    user = _selected_user(actor, criteria)
    users = reportable_users(actor, criteria).filter(pk=user.pk) if user else User.objects.none()
    return _unread_mandatory_rows(actor, criteria, users)


def _f08(actor: User, criteria: dict[str, Any]) -> ReportResult:
    user = _selected_user(actor, criteria)
    if user is None:
        return ReportResult(
            ("Message ID", "Title", "Read type", "Viewing seconds", "Printed", "Accessed"), []
        )
    receipts = MessageReceipt.objects.filter(
        user=user, message__in=reportable_messages(actor, criteria)
    )
    receipts = _within_period(receipts, "last_accessed_at", criteria)
    rows = [
        [
            receipt.message.message_id,
            receipt.message.current_version.title,
            "Read & Clear" if receipt.cleared_at else "Read" if receipt.first_read_at else "Unread",
            receipt.cumulative_view_seconds,
            "Yes" if receipt.printed_at else "No",
            _display_time(receipt.last_accessed_at),
        ]
        for receipt in receipts.select_related("message").prefetch_related("message__versions")
    ]
    return ReportResult(
        ("Message ID", "Title", "Read type", "Viewing seconds", "Printed", "Accessed"), rows
    )


def _f09(actor: User, criteria: dict[str, Any]) -> ReportResult:
    users = reportable_users(actor, criteria).prefetch_related("roles", "message_groups")
    rows = [
        [
            user.username,
            user.get_full_name(),
            ", ".join(user.roles.values_list("name", flat=True)),
            ", ".join(
                sorted(
                    {
                        group.primary_group.name
                        for group in user.message_groups.select_related("primary_group")
                    }
                )
            ),
        ]
        for user in users
    ]
    return ReportResult(("User ID", "User", "Roles", "Primary message groups"), rows)


def _f10(actor: User, criteria: dict[str, Any]) -> ReportResult:
    message = _selected_message(actor, criteria)
    if message is None:
        return ReportResult(("Field", "Value"), [])
    version = message.current_version
    rights = "; ".join(
        f"{right.message_group.code}: {right.get_right_display()}"
        for right in message.audience_rights.select_related("message_group")
    )
    return ReportResult(
        ("Field", "Value"),
        [
            ["Message ID", message.message_id],
            ["Kind", message.get_kind_display()],
            ["Title", version.title],
            ["Summary", version.summary],
            ["Subtype", str(message.subtype or "")],
            ["Status", message.get_status_display()],
            ["Originator", message.originator.username],
            ["Release", _display_time(version.release_at)],
            ["Effective", _display_time(version.effective_at)],
            ["Expiry", _display_time(version.expiry_at)],
            ["Audience rights", rights],
        ],
    )


def _f11(actor: User, criteria: dict[str, Any]) -> ReportResult:
    changes = ImportChangeRecord.objects.select_related("site")
    if not (actor.is_superuser or has_capability(actor, SEE_ALL_PMG)):
        if actor.site_id is None:
            changes = changes.none()
        else:
            changes = changes.filter(site_id=actor.site_id)
    if criteria.get("batch_reference"):
        changes = changes.filter(batch_reference__icontains=criteria["batch_reference"])
    changes = _within_period(changes, "occurred_at", criteria)
    rows = [
        [
            item.batch_reference,
            str(item.site),
            item.change_type,
            item.object_type,
            item.object_id,
            item.summary,
            _display_time(item.occurred_at),
        ]
        for item in changes
    ]
    return ReportResult(
        ("Batch", "Site", "Change", "Object type", "Object ID", "Summary", "Occurred"), rows
    )


def _f12(actor: User, criteria: dict[str, Any]) -> ReportResult:
    message = _selected_message(actor, criteria)
    if message is None:
        return ReportResult(("User ID", "User", "Accessed", "First access"), [])
    users = reportable_users(actor, criteria)
    first_access: dict[int, datetime] = {}
    access_events: QuerySet[MessageAccessEvent] = MessageAccessEvent.objects.filter(
        message=message, event_type=MessageAccessEvent.EventType.OPENED
    ).order_by("user_id", "occurred_at", "pk")
    access_events = _within_period(access_events, "occurred_at", criteria)
    for event in access_events:
        first_access.setdefault(event.user_id, event.occurred_at)
    cohort = criteria.get("access_cohort")
    rows = []
    for user in users.prefetch_related("message_groups"):
        if _right_for_user(user, message) is None:
            continue
        accessed = user.pk in first_access
        if cohort == "have" and not accessed:
            continue
        if cohort == "have_not" and accessed:
            continue
        rows.append(
            [
                user.username,
                user.get_full_name(),
                "HAVE" if accessed else "HAVE NOT",
                _display_time(first_access.get(user.pk)),
            ]
        )
    return ReportResult(("User ID", "User", "Accessed", "First access"), rows)


def _activity_rows(actor: User, criteria: dict[str, Any], users: QuerySet[User]) -> ReportResult:
    start, end = _period(criteria)
    events: list[list[Any]] = []
    logins = AuditEvent.objects.filter(action="identity.login.succeeded", actor__in=users)
    accesses = MessageAccessEvent.objects.filter(
        user__in=users, message__in=reportable_messages(actor, criteria)
    ).select_related("user", "message")
    if start:
        logins = logins.filter(occurred_at__gte=start)
        accesses = accesses.filter(occurred_at__gte=start)
    if end:
        logins = logins.filter(occurred_at__lte=end)
        accesses = accesses.filter(occurred_at__lte=end)
    for login in logins.select_related("actor"):
        if login.actor:
            events.append(
                [
                    login.actor.username,
                    login.actor.get_full_name(),
                    "Login",
                    "",
                    _display_time(login.occurred_at),
                ]
            )
    for access in accesses:
        events.append(
            [
                access.user.username,
                access.user.get_full_name(),
                access.get_event_type_display(),
                access.message.message_id,
                _display_time(access.occurred_at),
            ]
        )
    events.sort(key=lambda row: (row[4], row[0], row[2], row[3]))
    return ReportResult(("User ID", "User", "Activity", "Message ID", "Occurred"), events)


def _f13(actor: User, criteria: dict[str, Any]) -> ReportResult:
    users = reportable_users(actor, criteria)
    if criteria.get("message_group"):
        users = users.filter(message_groups__id=int(criteria["message_group"]))
    return _activity_rows(actor, criteria, users)


def _f14(actor: User, criteria: dict[str, Any]) -> ReportResult:
    now = timezone.now()
    reportee_ids = (
        SupervisorRelationship.objects.filter(supervisor=actor, starts_at__lte=now)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now))
        .values_list("reportee_id", flat=True)
    )
    users = reportable_users(actor, criteria).filter(pk__in=reportee_ids)
    return _activity_rows(actor, criteria, users)


REPORT_BUILDERS: dict[str, Callable[[User, dict[str, Any]], ReportResult]] = {
    "F01": _f01,
    "F02": _f02,
    "F03": _f03,
    "F04": _f04,
    "F05": _f05,
    "F06": _f06,
    "F07": _f07,
    "F08": _f08,
    "F09": _f09,
    "F10": _f10,
    "F11": _f11,
    "F12": _f12,
    "F13": _f13,
    "F14": _f14,
}


def build_report(actor: User, report_code: str, criteria: dict[str, Any]) -> ReportResult:
    require_capability(actor, VIEW_REPORTS)
    if report_code not in REPORT_BY_CODE:
        raise ValidationError("Unknown report.")
    result = REPORT_BUILDERS[report_code](actor, criteria)
    if len(result.rows) > MAX_SNAPSHOT_ROWS:
        raise ValidationError(f"Report exceeds the {MAX_SNAPSHOT_ROWS}-row safety limit.")
    return result


def serialise_criteria(criteria: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in criteria.items():
        if isinstance(value, date):
            output[key] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            output[key] = [str(item) for item in value]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            output[key] = value
        else:
            output[key] = str(value)
    return output


@transaction.atomic
def create_report_run(
    actor: User,
    report_code: str,
    criteria: dict[str, Any],
    *,
    force_async: bool = False,
) -> ReportRun:
    require_capability(actor, VIEW_REPORTS)
    clean_criteria = serialise_criteria(criteria)
    if force_async:
        run = ReportRun.objects.create(
            actor=actor,
            report_code=report_code,
            catalogue_version=CATALOGUE_VERSION,
            criteria=clean_criteria,
        )
        from firstbrief.reporting.tasks import generate_report

        transaction.on_commit(lambda: generate_report.delay(str(run.pk)))
        return run
    result = build_report(actor, report_code, clean_criteria)
    if len(result.rows) > ASYNC_ROW_THRESHOLD:
        return create_report_run(actor, report_code, clean_criteria, force_async=True)
    now = timezone.now()
    run = ReportRun.objects.create(
        actor=actor,
        report_code=report_code,
        catalogue_version=CATALOGUE_VERSION,
        criteria=clean_criteria,
        columns=list(result.columns),
        rows=result.rows,
        status=ReportRun.Status.COMPLETE,
        row_count=len(result.rows),
        started_at=now,
        completed_at=now,
    )
    record_event("report.generated", actor=actor, subject=run, after={"rows": run.row_count})
    return run


def execute_queued_report(run: ReportRun) -> ReportRun:
    run.status = ReportRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=("status", "started_at"))
    try:
        result = build_report(run.actor, run.report_code, run.criteria)
    except Exception as exc:
        run.status = ReportRun.Status.FAILED
        run.error = str(exc)[:500]
        run.completed_at = timezone.now()
        run.save(update_fields=("status", "error", "completed_at"))
        raise
    run.columns = list(result.columns)
    run.rows = result.rows
    run.row_count = len(result.rows)
    run.status = ReportRun.Status.COMPLETE
    run.completed_at = timezone.now()
    run.save(update_fields=("columns", "rows", "row_count", "status", "completed_at"))
    record_event("report.generated", actor=run.actor, subject=run, after={"rows": run.row_count})
    return run


def accessible_run(actor: User, run_id: uuid.UUID) -> ReportRun:
    try:
        run = ReportRun.objects.select_related("actor").get(pk=run_id)
    except ReportRun.DoesNotExist as exc:
        raise PermissionDenied("Report run is unavailable.") from exc
    if run.actor_id != actor.pk and not actor.is_superuser:
        raise PermissionDenied("Report run is unavailable.")
    require_capability(actor, VIEW_REPORTS)
    return run


def safe_csv_value(value: Any) -> str:
    text = str(value if value is not None else "")
    return f"'{text}" if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def render_report_pdf(run: ReportRun) -> bytes:
    if run.status != ReportRun.Status.COMPLETE:
        raise ValidationError("The report is not complete.")
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{run.report_code} report",
        author="FirstBrief",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"{run.report_code} - {REPORT_BY_CODE[run.report_code].title}", styles["Title"]),
        Paragraph(
            f"Generated {_display_time(run.completed_at)} by {run.actor.username}; "
            f"{run.row_count} rows.",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]
    table_data = [
        [Paragraph(str(column), styles["BodyText"]) for column in run.columns],
        *[
            [
                Paragraph(str(value if value is not None else ""), styles["BodyText"])
                for value in row
            ]
            for row in run.rows
        ],
    ]
    table = LongTable(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B8C2CC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return output.getvalue()
