"""Hostile-input-safe staging, exact preview and transactional commit."""

from __future__ import annotations

import csv
import hashlib
import io
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.configuration.models import MessageGroup, Site
from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_SAP_IMPORTS, require_capability
from firstbrief.reporting.models import ImportChangeRecord
from firstbrief.sapimport.models import ImportBatch, ImportChange

MAX_IMPORT_BYTES = 2 * 1024 * 1024
FIELDS = (
    "schema_version",
    "action",
    "user_id",
    "first_name",
    "last_name",
    "email",
    "site_code",
    "group_codes",
    "include_in_reports",
)


@dataclass(frozen=True)
class ParsedRow:
    row_number: int
    values: dict[str, str]


def _decode(content: bytes) -> str:
    if len(content) > MAX_IMPORT_BYTES:
        raise ValidationError("File exceeds the 2 MB limit.")
    if b"\x00" in content:
        raise ValidationError("Binary/NUL content is not permitted.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("File must be UTF-8 encoded.") from exc


def parse_csv(content: bytes) -> tuple[str, list[ParsedRow]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValidationError(f"Columns must exactly match: {', '.join(FIELDS)}.")
    rows: list[ParsedRow] = []
    seen: set[str] = set()
    try:
        for number, raw in enumerate(reader, start=2):
            values = {key: (value or "").strip() for key, value in raw.items()}
            if values["schema_version"] != "1":
                raise ValidationError(f"Row {number}: unsupported schema version.")
            if values["action"] not in {"upsert", "deactivate"}:
                raise ValidationError(f"Row {number}: action must be upsert or deactivate.")
            user_id = values["user_id"]
            if not user_id or user_id in seen:
                raise ValidationError(f"Row {number}: user ID is blank or duplicated.")
            seen.add(user_id)
            if not Site.objects.filter(code=values["site_code"], is_active=True).exists():
                raise ValidationError(f"Row {number}: unknown site code.")
            group_codes = [code for code in values["group_codes"].split("|") if code]
            valid_groups = MessageGroup.objects.filter(
                code__in=group_codes,
                primary_group__site__code=values["site_code"],
                is_active=True,
            ).count()
            if valid_groups != len(set(group_codes)):
                raise ValidationError(f"Row {number}: unknown or cross-site group.")
            if values["include_in_reports"].lower() not in {"true", "false", "1", "0"}:
                raise ValidationError(f"Row {number}: invalid Include in Reports value.")
            rows.append(ParsedRow(number, values))
    except csv.Error as exc:
        raise ValidationError(f"Malformed CSV: {exc}.") from exc
    if not rows:
        raise ValidationError("The file contains no data rows.")
    return text, rows


@transaction.atomic
def stage_import(*, actor: User, filename: str, content: bytes) -> ImportBatch:
    require_capability(actor, MANAGE_SAP_IMPORTS)
    digest = hashlib.sha256(content).hexdigest()
    safe_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:255]
    try:
        text, rows = parse_csv(content)
    except ValidationError as exc:
        batch = ImportBatch.objects.create(
            filename=safe_name,
            content_sha256=digest,
            staged_content="",
            status=ImportBatch.Status.REJECTED,
            error="; ".join(exc.messages),
            staged_by=actor,
        )
        record_event("sap_import.rejected", actor=actor, subject=batch)
        return batch
    batch = ImportBatch.objects.create(
        filename=safe_name,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        staged_content=text,
        status=ImportBatch.Status.STAGED,
        staged_by=actor,
    )
    ImportChange.objects.bulk_create(
        [
            ImportChange(
                batch=batch,
                row_number=row.row_number,
                site_code=row.values["site_code"],
                action=row.values["action"],
                user_id=row.values["user_id"],
                payload=row.values,
            )
            for row in rows
        ]
    )
    record_event("sap_import.staged", actor=actor, subject=batch, after={"rows": len(rows)})
    return batch


def changes_by_site(batch: ImportBatch) -> dict[str, list[ImportChange]]:
    grouped: dict[str, list[ImportChange]] = defaultdict(list)
    for change in batch.changes.all():
        grouped[change.site_code].append(change)
    return dict(grouped)


@transaction.atomic
def commit_import(*, actor: User, batch: ImportBatch, selected_ids: set[int]) -> ImportBatch:
    require_capability(actor, MANAGE_SAP_IMPORTS)
    locked = ImportBatch.objects.select_for_update().get(pk=batch.pk)
    if locked.status != ImportBatch.Status.STAGED:
        raise ValidationError("Only a staged import can be committed.")
    digest = hashlib.sha256(locked.staged_content.encode("utf-8")).hexdigest()
    # UTF-8 BOM is removed on staging, so compare the reviewed parsed rows as well.
    _, rows = parse_csv(locked.staged_content.encode("utf-8"))
    expected = {(row.row_number, row.values["user_id"]) for row in rows}
    actual = set(locked.changes.values_list("row_number", "user_id"))
    if digest != locked.content_sha256 or expected != actual:
        raise ValidationError("Staged content no longer matches its preview.")
    changes = locked.changes.select_for_update().filter(pk__in=selected_ids)
    for change in changes:
        values: dict[str, Any] = change.payload
        site = Site.objects.get(code=change.site_code)
        user = User.objects.filter(username=change.user_id).first()
        if change.action == "deactivate":
            if user is None:
                change.outcome = "No existing user; no change"
            else:
                user.is_active = False
                user.save(update_fields=("is_active",))
                change.applied = True
                change.outcome = "User deactivated"
        else:
            user, created = User.objects.update_or_create(
                username=change.user_id,
                defaults={
                    "first_name": values["first_name"],
                    "last_name": values["last_name"],
                    "email": values["email"],
                    "site": site,
                    "include_in_reports": values["include_in_reports"].lower() in {"true", "1"},
                    "imported_from_sap": True,
                    "is_active": True,
                    "local_auth_enabled": False,
                },
            )
            group_codes = [code for code in values["group_codes"].split("|") if code]
            user.message_groups.set(
                MessageGroup.objects.filter(code__in=group_codes, primary_group__site=site)
            )
            change.applied = True
            change.outcome = "User created" if created else "User updated"
        change.selected = True
        change.save(update_fields=("selected", "applied", "outcome"))
        ImportChangeRecord.objects.create(
            batch_reference=str(locked.pk),
            site=site,
            change_type=change.action,
            object_type="identity.user",
            object_id=change.user_id,
            summary=change.outcome,
            occurred_at=timezone.now(),
        )
    locked.changes.exclude(pk__in=selected_ids).update(selected=False)
    locked.status = ImportBatch.Status.COMMITTED
    locked.committed_at = timezone.now()
    locked.save(update_fields=("status", "committed_at"))
    record_event(
        "sap_import.committed",
        actor=actor,
        subject=locked,
        after={"selected": len(selected_ids), "applied": changes.filter(applied=True).count()},
    )
    return locked
