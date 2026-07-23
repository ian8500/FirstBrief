"""Cross-model integrity rules for configuration membership."""

from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from firstbrief.identity.models import User


@receiver(m2m_changed, sender=User.message_groups.through)
def enforce_exclusive_group_membership(
    sender: type, instance: User, action: str, pk_set: set[int] | None, **kwargs: object
) -> None:
    if action != "pre_add" or not pk_set:
        return
    existing_type_ids = set(
        instance.message_groups.filter(group_type__exclusive_membership=True).values_list(
            "group_type_id", flat=True
        )
    )
    from firstbrief.configuration.models import MessageGroup

    additions = MessageGroup.objects.filter(
        pk__in=pk_set, group_type__exclusive_membership=True
    ).values_list("group_type_id", flat=True)
    seen = existing_type_ids
    for type_id in additions:
        if type_id in seen:
            raise ValidationError(
                "A user may belong to only one message group of an exclusive group type."
            )
        seen.add(type_id)
