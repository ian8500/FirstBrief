from __future__ import annotations

from typing import Any

import pytest
from django.core.exceptions import ValidationError

from firstbrief.configuration.models import MessageGroup, PrimaryMessageGroup, Site
from firstbrief.identity.models import Capability, User
from firstbrief.identity.services import MANAGE_SAP_IMPORTS
from firstbrief.reporting.models import ImportChangeRecord
from firstbrief.sapimport.models import ImportBatch
from firstbrief.sapimport.services import commit_import, parse_csv, stage_import

pytestmark = pytest.mark.django_db

HEADER = (
    "schema_version,action,user_id,first_name,last_name,email,"
    "site_code,group_codes,include_in_reports\n"
)


@pytest.fixture
def import_data() -> dict[str, Any]:
    site = Site.objects.create(code="sap-site", name="SAP Site")
    pmg = PrimaryMessageGroup.objects.create(code="sap-pmg", name="SAP PMG", site=site)
    group = MessageGroup.objects.create(code="sap-ops", name="SAP Ops", primary_group=pmg)
    capability = Capability.objects.create(codename=MANAGE_SAP_IMPORTS, name="Manage SAP imports")
    actor = User.objects.create_user(username="sap-admin", password="Safe-test-42!", site=site)
    actor.direct_capabilities.add(capability)
    return {"site": site, "group": group, "actor": actor}


def test_stage_preview_commit_and_report_reconcile(import_data: dict[str, Any]) -> None:
    content = (
        HEADER
        + "1,upsert,sap-100,Ada,Import,ada@example.test,sap-site,sap-ops,true\n"
        + "1,upsert,sap-200,Ben,Import,ben@example.test,sap-site,sap-ops,false\n"
    ).encode()
    batch = stage_import(
        actor=import_data["actor"], filename="../../directory.csv", content=content
    )
    assert batch.filename == "directory.csv"
    assert batch.status == ImportBatch.Status.STAGED
    selected = {batch.changes.get(user_id="sap-100").pk}
    commit_import(actor=import_data["actor"], batch=batch, selected_ids=selected)
    imported = User.objects.get(username="sap-100")
    assert imported.imported_from_sap
    assert list(imported.message_groups.values_list("code", flat=True)) == ["sap-ops"]
    assert not User.objects.filter(username="sap-200").exists()
    assert ImportChangeRecord.objects.filter(
        batch_reference=str(batch.pk), object_id="sap-100"
    ).exists()


@pytest.mark.parametrize(
    "content,error",
    [
        (b"\x00binary", "Binary"),
        (b"\xff\xfe", "UTF-8"),
        ((HEADER + "2,upsert,x,A,B,e,sap-site,sap-ops,true\n").encode(), "schema"),
        (
            (HEADER + "1,upsert,x,A,B,e,sap-site,missing,true\n").encode(),
            "group",
        ),
    ],
)
def test_hostile_or_invalid_files_are_rejected(
    import_data: dict[str, Any], content: bytes, error: str
) -> None:
    batch = stage_import(actor=import_data["actor"], filename="bad.csv", content=content)
    assert batch.status == ImportBatch.Status.REJECTED
    assert error.lower() in batch.error.lower()


def test_duplicate_identity_is_rejected(import_data: dict[str, Any]) -> None:
    row = "1,upsert,dup,A,B,e,sap-site,sap-ops,true\n"
    with pytest.raises(ValidationError, match="duplicated"):
        parse_csv((HEADER + row + row).encode())
