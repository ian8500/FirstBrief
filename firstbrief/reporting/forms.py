"""Reusable report criteria with site-scoped reference choices."""

from __future__ import annotations

from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from firstbrief.configuration.models import (
    MessageGroup,
    PrimaryMessageGroup,
    Sector,
    Site,
)
from firstbrief.identity.models import Role, User
from firstbrief.identity.services import SEE_ALL_PMG, has_capability, visible_users_for
from firstbrief.reporting.models import ReportingCohort
from firstbrief.retrieval.services import search_messages


class ReportCriteriaForm(forms.Form):
    site = forms.ChoiceField(required=False)
    primary_group = forms.ChoiceField(required=False, label="Primary message group")
    message_group = forms.ChoiceField(required=False)
    associated_groups = forms.MultipleChoiceField(required=False)
    cohort = forms.ChoiceField(required=False, label="User/watch group")
    sector = forms.ChoiceField(required=False)
    user = forms.ChoiceField(required=False)
    role = forms.ChoiceField(required=False)
    message = forms.ChoiceField(required=False, label="Message ID")
    batch_reference = forms.CharField(required=False, max_length=100)
    access_cohort = forms.ChoiceField(
        required=False,
        choices=(("", "All users"), ("have", "HAVE accessed"), ("have_not", "HAVE NOT accessed")),
    )
    period_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    period_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    include_archived = forms.BooleanField(required=False)
    include_future = forms.BooleanField(required=False, label="Include not-yet-effective")
    force_async = forms.BooleanField(
        required=False,
        label="Generate in background",
        help_text="Use for large reports; you can return to the run later.",
    )

    def __init__(self, *args: Any, actor: User, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        all_sites = actor.is_superuser or has_capability(actor, SEE_ALL_PMG)
        sites = Site.objects.filter(is_active=True)
        primary_groups = PrimaryMessageGroup.objects.filter(is_active=True)
        message_groups = MessageGroup.objects.filter(is_active=True)
        sectors = Sector.objects.filter(is_active=True)
        cohorts = ReportingCohort.objects.filter(is_active=True)
        if not all_sites:
            if actor.site_id is None:
                sites = sites.none()
                primary_groups = primary_groups.none()
                message_groups = message_groups.none()
                sectors = sectors.none()
                cohorts = cohorts.none()
            else:
                sites = sites.filter(pk=actor.site_id)
                primary_groups = primary_groups.filter(site_id=actor.site_id)
                message_groups = message_groups.filter(primary_group__site_id=actor.site_id)
                sectors = sectors.filter(primary_group__site_id=actor.site_id)
                cohorts = cohorts.filter(site_id=actor.site_id)
        users = visible_users_for(actor).filter(include_in_reports=True)
        roles = Role.objects.filter(is_active=True)
        messages = search_messages(
            actor, {"include_archived": True, "include_future": True, "sort": "message_id"}
        )
        choices: dict[str, list[tuple[str, str]]] = {
            "site": [(str(item.pk), str(item)) for item in sites],
            "primary_group": [(str(item.pk), str(item)) for item in primary_groups],
            "message_group": [(str(item.pk), str(item)) for item in message_groups],
            "associated_groups": [(str(item.pk), str(item)) for item in message_groups],
            "cohort": [(str(item.pk), str(item)) for item in cohorts],
            "sector": [(str(item.pk), str(item)) for item in sectors],
            "user": [
                (
                    str(item.pk),
                    f"{item.first_name}, {item.last_name} ({item.username})",
                )
                for item in users.order_by("first_name", "last_name", "username")
            ],
            "role": [(str(item.pk), item.name) for item in roles],
            "message": [(str(item.pk), item.message_id) for item in messages],
        }
        for name, values in choices.items():
            field = self.fields[name]
            if isinstance(field, forms.MultipleChoiceField):
                field.choices = values
            elif isinstance(field, forms.ChoiceField):
                label = str(field.label or name.replace("_", " ")).lower()
                field.choices = [("", f"All permitted {label}s"), *values]

    def clean(self) -> dict[str, Any]:
        values = super().clean() or {}
        start = values.get("period_from")
        end = values.get("period_to")
        if start and end and start > end:
            raise ValidationError("Period start date must not be after the end date.")
        return values
