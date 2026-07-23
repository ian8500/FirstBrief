from __future__ import annotations

from datetime import timedelta
from typing import TypedDict

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client, RequestFactory
from django.utils import timezone

from firstbrief.assurance.models import AuditEvent
from firstbrief.configuration.models import MessageGroup, MessageType, PrimaryMessageGroup, Site
from firstbrief.identity.models import (
    Capability,
    IdentityPolicy,
    Role,
    SupervisorRelationship,
    User,
)
from firstbrief.identity.services import (
    MANAGE_USERS,
    SEE_ALL_PMG,
    can_access_message_type,
    has_capability,
    provision_local_user,
    require_capability,
    visible_users_for,
)

pytestmark = pytest.mark.django_db


class ScopedData(TypedDict):
    north: Site
    south: Site
    north_group: MessageGroup
    south_group: MessageGroup


@pytest.fixture
def scoped_data() -> ScopedData:
    north = Site.objects.create(code="north", name="North")
    south = Site.objects.create(code="south", name="South")
    north_pmg = PrimaryMessageGroup.objects.create(code="north-pmg", name="North PMG", site=north)
    south_pmg = PrimaryMessageGroup.objects.create(code="south-pmg", name="South PMG", site=south)
    north_group = MessageGroup.objects.create(
        code="north-ops",
        name="North Operations",
        primary_group=north_pmg,
    )
    south_group = MessageGroup.objects.create(
        code="south-ops",
        name="South Operations",
        primary_group=south_pmg,
    )
    return {
        "north": north,
        "south": south,
        "north_group": north_group,
        "south_group": south_group,
    }


def create_user(username: str, site: Site | None = None, password: str = "Safe-test-42!") -> User:
    return User.objects.create_user(
        username=username,
        first_name="Test",
        last_name="User",
        email=f"{username}@example.test",
        site=site,
        password=password,
        password_changed_at=timezone.now(),
    )


def test_valid_login_reaches_dashboard(client: Client) -> None:
    create_user("valid-user")
    response = client.post(
        "/access/login/",
        {"username": "valid-user", "password": "Safe-test-42!"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert AuditEvent.objects.filter(action="identity.login.succeeded").exists()


def test_invalid_login_is_generic_and_audited(client: Client) -> None:
    create_user("valid-user")
    response = client.post(
        "/access/login/",
        {"username": "valid-user", "password": "wrong"},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Sign in was unsuccessful" in content
    assert content.count("Please enter a correct username and password") == 1
    assert AuditEvent.objects.filter(action="identity.login.failed").exists()


def test_configurable_lockout_sends_no_password(rf: RequestFactory) -> None:
    policy = IdentityPolicy.load()
    policy.max_failed_logins = 2
    policy.account_lock_distribution_list = "security@example.test"
    policy.save()
    user = create_user("locked-user")
    request = rf.post("/access/login/", REMOTE_ADDR="192.0.2.20")
    assert authenticate(request, username=user.username, password="wrong") is None
    assert authenticate(request, username=user.username, password="wrong") is None
    user.refresh_from_db()
    assert user.locked_until is not None
    assert len(mail.outbox) == 1
    assert "password" not in mail.outbox[0].body.casefold()
    assert AuditEvent.objects.filter(action="identity.account.locked").exists()


def test_password_policy_enforces_length_categories_and_identity() -> None:
    user = User(username="ian8500", first_name="Ian", last_name="Dickson")
    with pytest.raises(ValidationError, match="at least 12"):
        validate_password("Short1!", user)
    with pytest.raises(ValidationError, match="user ID or name"):
        validate_password("ian8500-Secure-42!", user)
    validate_password("Unrelated-Secure-42!", user)


def test_default_group_must_be_membership(scoped_data: ScopedData) -> None:
    user = create_user("group-user", scoped_data["north"])
    user.default_message_group = scoped_data["north_group"]
    user.save()
    with pytest.raises(ValidationError, match="one of the memberships"):
        user.full_clean()
    user.message_groups.add(scoped_data["north_group"])
    user.full_clean()


def test_default_group_must_belong_to_site(scoped_data: ScopedData) -> None:
    user = create_user("cross-site-group", scoped_data["north"])
    user.default_message_group = scoped_data["south_group"]
    with pytest.raises(ValidationError, match="user's site"):
        user.full_clean()


def test_role_and_direct_capabilities_are_deny_by_default() -> None:
    permission = Capability.objects.create(codename=MANAGE_USERS, name="Manage users")
    role = Role.objects.create(name="Access administrators")
    user = create_user("operator")
    assert not has_capability(user, MANAGE_USERS)
    with pytest.raises(PermissionDenied):
        require_capability(user, MANAGE_USERS)
    role.capabilities.add(permission)
    user.roles.add(role)
    assert has_capability(user, MANAGE_USERS)
    user.roles.clear()
    user.direct_capabilities.add(permission)
    assert has_capability(user, MANAGE_USERS)


def test_site_scope_matrix(scoped_data: ScopedData) -> None:
    north_user = create_user("north-user", scoped_data["north"])
    create_user("south-user", scoped_data["south"])
    unscoped = create_user("unscoped")
    assert list(visible_users_for(north_user).values_list("username", flat=True)) == ["north-user"]
    assert not visible_users_for(unscoped).exists()
    see_all = Capability.objects.create(codename=SEE_ALL_PMG, name="See all PMGs")
    north_user.direct_capabilities.add(see_all)
    assert set(visible_users_for(north_user).values_list("username", flat=True)) == {
        "north-user",
        "south-user",
        "unscoped",
    }


def test_message_type_access_is_role_scoped() -> None:
    message_type = MessageType.objects.create(code="instruction", name="Instruction")
    other_type = MessageType.objects.create(code="botd", name="Brief of the Day")
    role = Role.objects.create(name="Instruction readers")
    role.message_types.add(message_type)
    user = create_user("reader")
    user.roles.add(role)
    assert can_access_message_type(user, message_type.pk)
    assert not can_access_message_type(user, other_type.pk)


def test_forced_password_change_blocks_other_authenticated_pages(client: Client) -> None:
    user = create_user("temporary-user")
    user.must_change_password = True
    user.save(update_fields=("must_change_password",))
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/access/password/change/"


def test_profile_is_read_only_and_lists_scope(client: Client, scoped_data: ScopedData) -> None:
    user = create_user("profile-user", scoped_data["north"])
    user.message_groups.add(scoped_data["north_group"])
    client.force_login(user)
    response = client.get("/access/profile/")
    assert response.status_code == 200
    assert "profile-user" in response.content.decode()
    assert "North Operations" in response.content.decode()


def test_user_management_requires_capability(client: Client) -> None:
    user = create_user("ordinary")
    client.force_login(user)
    assert client.get("/access/users/").status_code == 403


def test_provisioning_generates_one_time_password_and_audits(
    scoped_data: ScopedData,
) -> None:
    admin_user = create_user("access-admin", scoped_data["north"])
    permission = Capability.objects.create(codename=MANAGE_USERS, name="Manage users")
    admin_user.direct_capabilities.add(permission)
    new_user, password = provision_local_user(
        actor=admin_user,
        values={
            "username": "new-user",
            "first_name": "New",
            "last_name": "Person",
            "email": "new@example.test",
            "site": scoped_data["north"],
            "roles": [],
            "message_groups": [scoped_data["north_group"]],
            "default_message_group": scoped_data["north_group"],
        },
    )
    assert new_user.check_password(password)
    assert new_user.must_change_password
    assert AuditEvent.objects.filter(action="identity.user.created").exists()
    event = AuditEvent.objects.first()
    assert event is not None
    assert password not in str(event.after)


def test_audit_events_cannot_be_changed_or_deleted() -> None:
    event = AuditEvent.objects.create(action="test", object_type="test")
    event.reason = "mutated"
    with pytest.raises(TypeError, match="append-only"):
        event.save()
    with pytest.raises(TypeError, match="append-only"):
        AuditEvent.objects.filter(pk=event.pk).update(reason="mutated")
    with pytest.raises(TypeError, match="append-only"):
        AuditEvent.objects.filter(pk=event.pk).delete()


def test_password_expiry_forces_change(rf: RequestFactory) -> None:
    policy = IdentityPolicy.load()
    policy.password_expiry_days = 30
    policy.save()
    user = create_user("expired-user")
    user.password_changed_at = timezone.now() - timedelta(days=31)
    user.save(update_fields=("password_changed_at",))
    authenticated = authenticate(
        rf.post("/access/login/"),
        username=user.username,
        password="Safe-test-42!",
    )
    assert authenticated is not None
    authenticated.refresh_from_db()
    assert authenticated.must_change_password


def test_unknown_disabled_and_locked_accounts_are_denied(rf: RequestFactory) -> None:
    request = rf.post("/access/login/")
    assert authenticate(request, username="missing", password="Something-42!") is None
    disabled = create_user("disabled")
    disabled.local_auth_enabled = False
    disabled.save(update_fields=("local_auth_enabled",))
    assert authenticate(request, username=disabled.username, password="Safe-test-42!") is None
    disabled.local_auth_enabled = True
    disabled.locked_until = timezone.now() + timedelta(minutes=5)
    disabled.save(update_fields=("local_auth_enabled", "locked_until"))
    assert authenticate(request, username=disabled.username, password="Safe-test-42!") is None


def test_user_administration_browser_flow(
    client: Client,
    scoped_data: ScopedData,
) -> None:
    actor = create_user("manager", scoped_data["north"])
    permission = Capability.objects.create(codename=MANAGE_USERS, name="Manage users")
    actor.direct_capabilities.add(permission)
    role = Role.objects.create(name="Operators")
    group = scoped_data["north_group"]
    client.force_login(actor)

    short_search = client.get("/access/users/?q=ab")
    assert short_search.status_code == 200
    assert "at least three" in short_search.content.decode()
    assert client.get("/access/users/create/").status_code == 200
    created = client.post(
        "/access/users/create/",
        {
            "username": "created-user",
            "first_name": "Created",
            "last_name": "User",
            "email": "created@example.test",
            "site": scoped_data["north"].pk,
            "roles": [role.pk],
            "message_groups": [group.pk],
            "default_message_group": group.pk,
            "include_in_reports": "on",
        },
    )
    assert created.status_code == 302
    redirect_location = created["Location"]
    temporary = client.get(redirect_location)
    assert temporary.status_code == 200
    assert "will not be shown again" in temporary.content.decode()
    assert client.get(redirect_location).status_code == 302

    target = User.objects.get(username="created-user")
    search = client.get("/access/users/?q=cre")
    assert "Created, User (created-user)" in search.content.decode()
    reset = client.post(f"/access/users/{target.pk}/reset/")
    assert reset.status_code == 302
    target.refresh_from_db()
    assert target.must_change_password


def test_user_form_rejects_default_outside_memberships(
    client: Client,
    scoped_data: ScopedData,
) -> None:
    actor = create_user("manager-two", scoped_data["north"])
    permission = Capability.objects.create(codename=MANAGE_USERS, name="Manage users")
    actor.direct_capabilities.add(permission)
    client.force_login(actor)
    response = client.post(
        "/access/users/create/",
        {
            "username": "invalid-user",
            "first_name": "Invalid",
            "last_name": "User",
            "site": scoped_data["north"].pk,
            "message_groups": [scoped_data["north_group"].pk],
            "default_message_group": scoped_data["south_group"].pk,
        },
    )
    assert response.status_code == 200
    assert "Default group must be one of the memberships" in response.content.decode()


def test_password_change_and_logout_flows(client: Client) -> None:
    user = create_user("self-service")
    user.must_change_password = True
    user.save(update_fields=("must_change_password",))
    client.force_login(user)
    changed = client.post(
        "/access/password/change/",
        {
            "old_password": "Safe-test-42!",
            "new_password1": "Replacement-Secure-84!",
            "new_password2": "Replacement-Secure-84!",
        },
    )
    assert changed.status_code == 302
    user.refresh_from_db()
    assert not user.must_change_password
    assert AuditEvent.objects.filter(action="identity.password.changed").exists()
    client.get("/access/logout/")
    logged_out = client.post("/access/logout/")
    assert logged_out.status_code == 302
    assert AuditEvent.objects.filter(action="identity.logout").exists()


def test_policy_and_supervisor_validation() -> None:
    policy = IdentityPolicy.load()
    policy.password_warning_days = policy.password_expiry_days
    with pytest.raises(ValidationError, match="shorter than expiry"):
        policy.full_clean()
    policy.password_warning_days = 1
    policy.password_min_length = 100
    policy.password_max_length = 64
    with pytest.raises(ValidationError, match="Minimum exceeds"):
        policy.full_clean()
    user = create_user("self-supervisor")
    relationship = SupervisorRelationship(
        supervisor=user,
        reportee=user,
        starts_at=timezone.now(),
    )
    with pytest.raises(ValidationError, match="supervise themselves"):
        relationship.full_clean()


def test_development_seed_is_opt_in(
    settings: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.ENVIRONMENT = "development"  # type: ignore[attr-defined]
    monkeypatch.setenv(
        "FIRSTBRIEF_DEVELOPMENT_ADMIN_PASSWORD",
        "Completely-Unrelated-42!",
    )
    call_command("seed_development", verbosity=0)
    user = User.objects.get(username="demo-admin")
    assert user.check_password("Completely-Unrelated-42!")
    assert Role.objects.get(name="System administrator").message_types.count() == 2
