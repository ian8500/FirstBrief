"""Transactional, audited mutations for configuration objects."""

from typing import Any

from django.db import transaction

from firstbrief.assurance.services import record_event
from firstbrief.identity.models import User
from firstbrief.identity.services import MANAGE_CONFIGURATION, require_capability


@transaction.atomic
def save_configuration(*, actor: User, form: Any) -> Any:
    require_capability(actor, MANAGE_CONFIGURATION)
    instance = form.instance
    before = {}
    if instance.pk:
        before = {
            field.name: str(getattr(instance.__class__.objects.get(pk=instance.pk), field.name))
            for field in instance._meta.fields
        }
    saved = form.save()
    record_event(
        "configuration.updated" if before else "configuration.created",
        actor=actor,
        subject=saved,
        before=before,
        after={"code": saved.code, "name": saved.name},
    )
    return saved


@transaction.atomic
def delete_configuration(*, actor: User, instance: Any) -> None:
    require_capability(actor, MANAGE_CONFIGURATION)
    record_event(
        "configuration.deleted",
        actor=actor,
        subject=instance,
        before={"code": instance.code, "name": instance.name},
    )
    instance.delete()
