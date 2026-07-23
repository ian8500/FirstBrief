"""Authorisation, site-scope and local-account domain services."""

from __future__ import annotations

import secrets
import string
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import IdentityPolicy, User

MANAGE_USERS = "manage-users"
MANAGE_ROLES = "manage-roles"
MANAGE_IDENTITY_SETTINGS = "manage-identity-settings"
MANAGE_CONFIGURATION = "manage-configuration"
CREATE_MESSAGES = "create-messages"
APPROVE_MESSAGES = "approve-messages"
MANAGE_MESSAGES = "manage-messages"
SEE_ALL_PMG = "see-all-primary-message-groups"


def has_capability(user: User, codename: str) -> bool:
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return (
        user.direct_capabilities.filter(codename=codename).exists()
        or user.roles.filter(
            is_active=True,
            capabilities__codename=codename,
        ).exists()
    )


def require_capability(user: User, codename: str) -> None:
    if not has_capability(user, codename):
        raise PermissionDenied("You do not have permission to perform this action.")


def visible_users_for(actor: User) -> QuerySet[User]:
    queryset = User.objects.select_related("site").prefetch_related("roles", "message_groups")
    if actor.is_superuser or has_capability(actor, SEE_ALL_PMG):
        return queryset
    if not actor.site_id:
        return queryset.none()
    return queryset.filter(site_id=actor.site_id)


def can_access_message_type(user: User, message_type_id: int) -> bool:
    if user.is_superuser:
        return True
    return user.roles.filter(
        is_active=True,
        message_types__id=message_type_id,
    ).exists()


def validate_default_group(user: User, group_ids: list[int]) -> None:
    if user.default_message_group_id and user.default_message_group_id not in group_ids:
        raise ValidationError(
            {"default_message_group": "Default group must be one of the memberships."}
        )


def generate_compliant_password(user: User) -> str:
    policy = IdentityPolicy.load()
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-=?"
    length = min(max(policy.password_min_length, 16), policy.password_max_length)
    for _ in range(100):
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_password(password, user)
        except ValidationError:
            continue
        return password
    raise RuntimeError("Unable to generate a compliant password")


@transaction.atomic
def provision_local_user(*, actor: User, values: dict[str, Any]) -> tuple[User, str]:
    require_capability(actor, MANAGE_USERS)
    roles = list(values.pop("roles", []))
    groups = list(values.pop("message_groups", []))
    user = User(**values)
    password = generate_compliant_password(user)
    user.set_password(password)
    user.must_change_password = True
    user.password_changed_at = timezone.now()
    user.full_clean(exclude=("password",))
    user.save()
    user.roles.set(roles)
    user.message_groups.set(groups)
    validate_default_group(user, [group.pk for group in groups])
    record_event(
        "identity.user.created",
        actor=actor,
        subject=user,
        after={"username": user.username, "site_id": user.site_id},
    )
    return user, password


@transaction.atomic
def reset_local_password(*, actor: User, user: User) -> str:
    require_capability(actor, MANAGE_USERS)
    password = generate_compliant_password(user)
    user.set_password(password)
    user.must_change_password = True
    user.password_changed_at = timezone.now()
    user.failed_login_count = 0
    user.locked_until = None
    user.save(
        update_fields=(
            "password",
            "must_change_password",
            "password_changed_at",
            "failed_login_count",
            "locked_until",
        )
    )
    record_event("identity.password.admin_reset", actor=actor, subject=user)
    return password
