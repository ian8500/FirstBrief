"""Accessible administration forms for the configuration taxonomy."""

from typing import Any, ClassVar

from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import SafeString

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


class DualListSelectMultiple(forms.SelectMultiple):
    template_name = "configuration/widgets/dual_list.html"

    def render(
        self,
        name: str,
        value: object,
        attrs: dict[str, object] | None = None,
        renderer: object | None = None,
    ) -> SafeString:
        context = self.get_context(name, value, attrs)
        return SafeString(render_to_string(self.template_name, context))


class ConfigurationForm(forms.ModelForm):  # type: ignore[type-arg]
    def save(self, commit: bool = True):  # type: ignore[no-untyped-def]
        instance = super().save(commit=False)
        instance.full_clean()
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SiteForm(ConfigurationForm):
    class Meta:
        model = Site
        fields = ("code", "name", "is_active")


class PrimaryMessageGroupForm(ConfigurationForm):
    class Meta:
        model = PrimaryMessageGroup
        fields = ("code", "name", "site", "is_active")


class MessageGroupTypeForm(ConfigurationForm):
    class Meta:
        model = MessageGroupType
        fields = (
            "code",
            "name",
            "parent",
            "exclusive_membership",
            "allowed_message_types",
            "is_active",
        )
        widgets: ClassVar[dict[str, object]] = {
            "allowed_message_types": DualListSelectMultiple,
        }


class MessageGroupForm(ConfigurationForm):
    class Meta:
        model = MessageGroup
        fields = (
            "code",
            "name",
            "primary_group",
            "parent",
            "group_type",
            "sectors",
            "is_active",
        )
        widgets: ClassVar[dict[str, object]] = {"sectors": DualListSelectMultiple}


class MessageTypeForm(ConfigurationForm):
    class Meta:
        model = MessageType
        fields = (
            "code",
            "name",
            "default_content_type",
            "view_mode",
            "menu_view",
            "display_at_logon",
            "requires_approval",
            "searchable",
            "has_subtypes",
            "has_effective_date",
            "is_active",
        )


class MessageSubTypeForm(ConfigurationForm):
    class Meta:
        model = MessageSubType
        fields = (
            "code",
            "name",
            "primary_group",
            "message_type",
            "minimum_validity_days",
            "maximum_validity_days",
            "email_distributions",
            "is_active",
        )
        widgets: ClassVar[dict[str, object]] = {
            "email_distributions": DualListSelectMultiple,
        }


class SectorForm(ConfigurationForm):
    class Meta:
        model = Sector
        fields = ("code", "name", "identification", "primary_group", "is_active")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for field_name in ("code", "identification", "primary_group"):
                self.fields[field_name].disabled = True


class EmailDistributionForm(ConfigurationForm):
    class Meta:
        model = EmailDistribution
        fields = ("code", "name", "email_address", "use_as_email", "is_active")
