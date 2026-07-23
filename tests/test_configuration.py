from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.forms import SectorForm
from firstbrief.configuration.models import (
    EmailDistribution,
    MessageGroup,
    MessageGroupType,
    MessageSubType,
    MessageType,
    PrimaryMessageGroup,
    Sector,
    Site,
)
from firstbrief.identity.models import Capability, User
from firstbrief.identity.services import MANAGE_CONFIGURATION

pytestmark = pytest.mark.django_db


@pytest.fixture
def taxonomy() -> dict[str, object]:
    site = Site.objects.create(code="central", name="Central")
    pmg = PrimaryMessageGroup.objects.create(code="central-pmg", name="Central PMG", site=site)
    group_type = MessageGroupType.objects.create(
        code="desk", name="Desk", exclusive_membership=True
    )
    group = MessageGroup.objects.create(
        code="control", name="Control", primary_group=pmg, group_type=group_type
    )
    return {"site": site, "pmg": pmg, "group_type": group_type, "group": group}


def test_hierarchies_reject_cycles_and_cross_primary_group(taxonomy: dict[str, object]) -> None:
    group = taxonomy["group"]
    assert isinstance(group, MessageGroup)
    child = MessageGroup.objects.create(
        code="child", name="Child", primary_group=taxonomy["pmg"], parent=group
    )
    group.parent = child
    with pytest.raises(ValidationError):
        group.full_clean()

    other_site = Site.objects.create(code="other", name="Other")
    other_pmg = PrimaryMessageGroup.objects.create(
        code="other-pmg", name="Other PMG", site=other_site
    )
    child.primary_group = other_pmg
    with pytest.raises(ValidationError):
        child.full_clean()


def test_group_deletion_is_protected_for_children_and_memberships(
    taxonomy: dict[str, object],
) -> None:
    group = taxonomy["group"]
    assert isinstance(group, MessageGroup)
    MessageGroup.objects.create(
        code="child", name="Child", primary_group=taxonomy["pmg"], parent=group
    )
    with pytest.raises(ProtectedError):
        group.delete()

    member_group = MessageGroup.objects.create(
        code="member-group", name="Member Group", primary_group=taxonomy["pmg"]
    )
    user = User.objects.create_user(username="member", password="Safe-test-42!")
    user.message_groups.add(member_group)
    with pytest.raises(ProtectedError):
        member_group.delete()


def test_group_type_deletion_is_protected(taxonomy: dict[str, object]) -> None:
    group_type = taxonomy["group_type"]
    assert isinstance(group_type, MessageGroupType)
    with pytest.raises(ProtectedError):
        group_type.delete()


def test_exclusive_group_type_blocks_second_membership(taxonomy: dict[str, object]) -> None:
    group = taxonomy["group"]
    group_type = taxonomy["group_type"]
    assert isinstance(group, MessageGroup)
    second = MessageGroup.objects.create(
        code="second", name="Second", primary_group=taxonomy["pmg"], group_type=group_type
    )
    user = User.objects.create_user(username="exclusive", password="Safe-test-42!")
    user.message_groups.add(group)
    with pytest.raises(ValidationError), transaction.atomic():
        user.message_groups.add(second)
    assert list(user.message_groups.all()) == [group]


def test_subtype_validity_and_distribution_protection(taxonomy: dict[str, object]) -> None:
    message_type = MessageType.objects.create(code="notice", name="Notice", has_subtypes=True)
    distribution = EmailDistribution.objects.create(
        code="ops", name="Operations", email_address="ops@example.test"
    )
    subtype = MessageSubType.objects.create(
        code="urgent",
        name="Urgent",
        primary_group=taxonomy["pmg"],
        message_type=message_type,
        minimum_validity_days=1,
        maximum_validity_days=7,
    )
    subtype.email_distributions.add(distribution)
    with pytest.raises(ProtectedError):
        distribution.delete()

    with pytest.raises(IntegrityError), transaction.atomic():
        MessageSubType.objects.create(
            code="invalid",
            name="Invalid",
            primary_group=taxonomy["pmg"],
            message_type=message_type,
            minimum_validity_days=8,
            maximum_validity_days=7,
        )


def test_subtype_requires_enabled_message_type(taxonomy: dict[str, object]) -> None:
    message_type = MessageType.objects.create(code="plain", name="Plain")
    subtype = MessageSubType(
        code="not-allowed",
        name="Not allowed",
        primary_group=taxonomy["pmg"],
        message_type=message_type,
    )
    with pytest.raises(ValidationError):
        subtype.full_clean()


def test_sector_immutable_fields_are_disabled_on_edit(taxonomy: dict[str, object]) -> None:
    sector = Sector.objects.create(
        code="s1", name="Sector One", identification="ID-1", primary_group=taxonomy["pmg"]
    )
    form = SectorForm(instance=sector)
    assert form.fields["code"].disabled
    assert form.fields["identification"].disabled
    assert form.fields["primary_group"].disabled
    assert not form.fields["name"].disabled


def test_configuration_ui_requires_permission_and_audits_create(
    client: Client, taxonomy: dict[str, object]
) -> None:
    user = User.objects.create_user(username="config-admin", password="Safe-test-42!")
    client.force_login(user)
    assert client.get("/configuration/").status_code == 403
    capability = Capability.objects.create(
        codename=MANAGE_CONFIGURATION, name="Manage configuration"
    )
    user.direct_capabilities.add(capability)
    response = client.post(
        "/configuration/distributions/new/",
        {
            "code": "briefing",
            "name": "Briefing",
            "email_address": "briefing@example.test",
            "use_as_email": "on",
            "is_active": "on",
        },
    )
    assert response.status_code == 302
    assert EmailDistribution.objects.filter(code="briefing").exists()
    assert AuditEvent.objects.filter(action="configuration.created").exists()


def test_configuration_form_shows_validation_summary(
    client: Client, taxonomy: dict[str, object]
) -> None:
    user = User.objects.create_superuser(username="root", password="Safe-test-42!")
    client.force_login(user)
    response = client.post("/configuration/sectors/new/", {"code": ""})
    assert response.status_code == 200
    assert b"There is a problem" in response.content


def test_dual_list_widget_renders_in_configuration_form(
    client: Client, taxonomy: dict[str, object]
) -> None:
    user = User.objects.create_superuser(username="widget-admin", password="Safe-test-42!")
    client.force_login(user)
    response = client.get("/configuration/group-types/new/")
    assert response.status_code == 200
    assert b"data-dual-list" in response.content
    assert b"Add all" in response.content
    assert b"Remove all" in response.content
