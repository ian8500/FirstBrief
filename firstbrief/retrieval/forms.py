"""Validated search criteria with actor-scoped choices."""

from __future__ import annotations

from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from firstbrief.configuration.models import MessageGroup, MessageSubType
from firstbrief.identity.models import User
from firstbrief.identity.services import SEE_ALL_PMG, has_capability
from firstbrief.messaging.models import Message


class MessageSearchForm(forms.Form):
    SORT_CHOICES = (
        ("message_id", "Message ID"),
        ("title", "Title"),
        ("release", "Release"),
        ("effective", "Effective"),
        ("expiry", "Expiry"),
        ("status", "Status"),
    )
    READ_CHOICES = (
        ("", "Any read status"),
        ("unread", "Unread"),
        ("read", "Read"),
        ("cleared", "Read & Cleared"),
    )

    kind = forms.ChoiceField(
        required=False, choices=(("", "BOTD and Instructions"), *Message.Kind.choices)
    )
    message_id = forms.CharField(required=False, max_length=80, label="Message ID")
    title = forms.CharField(required=False, max_length=240)
    summary = forms.CharField(required=False, max_length=240)
    content = forms.CharField(required=False, max_length=240, label="Display content")
    group = forms.ChoiceField(required=False)
    subtype = forms.ChoiceField(required=False)
    read_status = forms.ChoiceField(required=False, choices=READ_CHOICES)
    release_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    release_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    effective_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    effective_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    expiry_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    expiry_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    include_archived = forms.BooleanField(required=False)
    include_future = forms.BooleanField(required=False, label="Include not-yet-effective")
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES, initial="message_id")
    direction = forms.ChoiceField(
        required=False,
        choices=(("asc", "Ascending"), ("desc", "Descending")),
        initial="asc",
    )

    def __init__(self, *args: Any, actor: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        groups = MessageGroup.objects.filter(is_active=True)
        subtypes = MessageSubType.objects.filter(is_active=True)
        if not actor.is_superuser and not has_capability(actor, SEE_ALL_PMG):
            if actor.site_id is None:
                groups = groups.none()
                subtypes = subtypes.none()
            else:
                groups = groups.filter(primary_group__site_id=actor.site_id)
                subtypes = subtypes.filter(primary_group__site_id=actor.site_id)
        group_field = self.fields["group"]
        subtype_field = self.fields["subtype"]
        assert isinstance(group_field, forms.ChoiceField)
        assert isinstance(subtype_field, forms.ChoiceField)
        group_field.choices = [
            ("", "All permitted groups"),
            *((str(item.pk), str(item)) for item in groups.order_by("name", "pk")),
        ]
        subtype_field.choices = [
            ("", "All permitted subtypes"),
            *((str(item.pk), str(item)) for item in subtypes.order_by("name", "pk")),
        ]

    def clean(self) -> dict[str, Any]:
        values = super().clean() or {}
        for prefix in ("release", "effective", "expiry"):
            start = values.get(f"{prefix}_from")
            end = values.get(f"{prefix}_to")
            if start and end and start > end:
                raise ValidationError(
                    f"{prefix.title()} start date must not be after its end date."
                )
        return values
