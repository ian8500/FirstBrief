"""Versioned report catalogue definitions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportDefinition:
    code: str
    title: str
    description: str


CATALOGUE_VERSION = 1

REPORTS = (
    ReportDefinition("F01", "BOTD group members", "Members of a selected BOTD message group."),
    ReportDefinition("F02", "Site members", "Users assigned to a selected site."),
    ReportDefinition("F03", "User group members", "Members of a reporting user group."),
    ReportDefinition("F04", "Watch group members", "Members of a reporting watch group."),
    ReportDefinition("F05", "Sector message groups", "Message groups mapped to a sector."),
    ReportDefinition(
        "F06",
        "Group unread mandatory",
        "Users in selected groups and their unread mandatory messages.",
    ),
    ReportDefinition(
        "F07", "User unread mandatory", "Unread mandatory messages for a selected user."
    ),
    ReportDefinition(
        "F08",
        "User reading activity",
        "Read type, viewing time and printed status for a selected user.",
    ),
    ReportDefinition("F09", "Users by role and PMG", "Users filtered by role and primary group."),
    ReportDefinition("F10", "Message details", "Full configuration for a selected message."),
    ReportDefinition("F11", "Import updates", "Changes committed by an external import batch."),
    ReportDefinition(
        "F12", "Message access cohort", "Users who have or have not accessed a message."
    ),
    ReportDefinition(
        "F13", "Group activity", "Login and effective-message activity for selected groups."
    ),
    ReportDefinition(
        "F14", "Reportee activity", "Login and effective-message activity for direct reportees."
    ),
)

REPORT_BY_CODE = {definition.code: definition for definition in REPORTS}
