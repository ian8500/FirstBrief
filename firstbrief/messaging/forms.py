"""Accessible message authoring and lifecycle command forms."""

from __future__ import annotations

from typing import Any, ClassVar, cast

from django import forms

from firstbrief.configuration.models import MessageGroup, MessageSubType, MessageType
from firstbrief.identity.models import User
from firstbrief.identity.services import SEE_ALL_PMG, has_capability
from firstbrief.messaging.models import Message, MessageAudienceRight


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self) -> None:
        super().__init__(format="%Y-%m-%dT%H:%M")


class MessageCreateForm(forms.Form):
    message_id = forms.SlugField(max_length=80, label="Message ID")
    kind = forms.ChoiceField(choices=Message.Kind.choices)
    message_type = forms.ModelChoiceField(queryset=MessageType.objects.filter(is_active=True))
    subtype = forms.ModelChoiceField(
        queryset=MessageSubType.objects.filter(is_active=True),
        required=False,
    )
    title = forms.CharField(max_length=240)
    summary = forms.CharField(widget=forms.Textarea, required=False)
    text_content = forms.CharField(widget=forms.Textarea, required=False)
    release_at = forms.DateTimeField(widget=DateTimeLocalInput())
    effective_at = forms.DateTimeField(widget=DateTimeLocalInput(), required=False)
    expiry_at = forms.DateTimeField(widget=DateTimeLocalInput())
    archive_on_expiry = forms.BooleanField(required=False, initial=True)
    all_sites = forms.BooleanField(
        required=False,
        help_text="Target every active message group as Allowed.",
    )
    mandatory_groups = forms.ModelMultipleChoiceField(
        queryset=MessageGroup.objects.filter(is_active=True), required=False
    )
    allowed_groups = forms.ModelMultipleChoiceField(
        queryset=MessageGroup.objects.filter(is_active=True), required=False
    )
    prohibited_groups = forms.ModelMultipleChoiceField(
        queryset=MessageGroup.objects.filter(is_active=True), required=False
    )
    approvers = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True), required=False
    )
    display_pdf = forms.FileField(required=False, label="Display PDF")
    print_pdf = forms.FileField(required=False, label="Print PDF")

    datetime_fields: ClassVar[tuple[str, ...]] = ("release_at", "effective_at", "expiry_at")

    def __init__(self, *args: Any, actor: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        groups = MessageGroup.objects.filter(is_active=True)
        subtypes = MessageSubType.objects.filter(is_active=True)
        approvers = User.objects.filter(is_active=True)
        if actor is not None and not actor.is_superuser and not has_capability(actor, SEE_ALL_PMG):
            site_id = actor.site_id
            if site_id is None:
                groups = groups.none()
                subtypes = subtypes.none()
                approvers = approvers.none()
            else:
                groups = groups.filter(primary_group__site_id=site_id)
                subtypes = subtypes.filter(primary_group__site_id=site_id)
                approvers = approvers.filter(site_id=site_id)
        self.available_groups = groups
        for field_name in ("mandatory_groups", "allowed_groups", "prohibited_groups"):
            cast(
                "forms.ModelMultipleChoiceField[MessageGroup]", self.fields[field_name]
            ).queryset = groups
        cast("forms.ModelChoiceField[MessageSubType]", self.fields["subtype"]).queryset = subtypes
        cast("forms.ModelMultipleChoiceField[User]", self.fields["approvers"]).queryset = approvers

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        kind = cleaned.get("kind")
        message_type = cleaned.get("message_type")
        subtype = cleaned.get("subtype")
        if message_type:
            if message_type.has_subtypes and not subtype:
                self.add_error("subtype", "This message type requires a subtype.")
            if subtype and subtype.message_type_id != message_type.pk:
                self.add_error("subtype", "Subtype must belong to the selected message type.")
        if kind == Message.Kind.INSTRUCTION:
            if not cleaned.get("display_pdf"):
                self.add_error("display_pdf", "Instruction Display PDF is required.")
            if not cleaned.get("print_pdf"):
                self.add_error("print_pdf", "Instruction Print PDF is required.")
        elif kind == Message.Kind.BOTD and not str(cleaned.get("text_content", "")).strip():
            self.add_error("text_content", "BOTD message content is required.")

        mandatory = set(cleaned.get("mandatory_groups") or [])
        allowed = set(cleaned.get("allowed_groups") or [])
        prohibited = set(cleaned.get("prohibited_groups") or [])
        if cleaned.get("all_sites"):
            allowed = set(self.available_groups)
            cleaned["allowed_groups"] = allowed
        overlap = (mandatory & allowed) | (mandatory & prohibited) | (allowed & prohibited)
        if overlap:
            self.add_error(None, "A message group can have only one audience right.")
        if not mandatory and not allowed:
            self.add_error(None, "Select at least one Mandatory or Allowed group.")
        if subtype and not cleaned.get("all_sites"):
            selected_pmgs = {group.primary_group_id for group in mandatory | allowed | prohibited}
            if subtype.primary_group_id not in selected_pmgs:
                self.add_error(
                    "subtype",
                    "Subtype must belong to one of the selected Primary Message Groups.",
                )
        return cleaned

    def group_rights(self) -> dict[int, str]:
        if self.cleaned_data["all_sites"]:
            return {group.pk: MessageAudienceRight.Right.ALLOWED for group in self.available_groups}
        rights: dict[int, str] = {}
        for field, right in (
            ("mandatory_groups", MessageAudienceRight.Right.MANDATORY),
            ("allowed_groups", MessageAudienceRight.Right.ALLOWED),
            ("prohibited_groups", MessageAudienceRight.Right.PROHIBITED),
        ):
            rights.update({group.pk: right for group in self.cleaned_data[field]})
        return rights


class LifecycleActionForm(forms.Form):
    expected_version = forms.IntegerField(widget=forms.HiddenInput)
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(widget=forms.Textarea, required=False)
    validity_justification = forms.CharField(widget=forms.Textarea, required=False)
    future_expiry_at = forms.DateTimeField(widget=DateTimeLocalInput(), required=False)


class MessageRevisionForm(MessageCreateForm):
    reason = forms.CharField(widget=forms.Textarea)

    def __init__(
        self, *args: Any, message: Message, actor: User | None = None, **kwargs: Any
    ) -> None:
        version = message.current_version
        rights = {
            right: list(
                message.audience_rights.filter(right=right).values_list(
                    "message_group_id", flat=True
                )
            )
            for right in MessageAudienceRight.Right.values
        }
        initial = {
            "message_id": message.message_id,
            "kind": message.kind,
            "message_type": message.message_type_id,
            "subtype": message.subtype_id,
            "title": version.title,
            "summary": version.summary,
            "text_content": version.text_content,
            "release_at": version.release_at,
            "effective_at": version.effective_at,
            "expiry_at": version.expiry_at,
            "archive_on_expiry": message.archive_on_expiry,
            "mandatory_groups": rights[MessageAudienceRight.Right.MANDATORY],
            "allowed_groups": rights[MessageAudienceRight.Right.ALLOWED],
            "prohibited_groups": rights[MessageAudienceRight.Right.PROHIBITED],
            "approvers": list(message.approvers.values_list("pk", flat=True)),
        }
        initial.update(kwargs.pop("initial", {}) or {})
        kwargs["initial"] = initial
        super().__init__(*args, actor=actor, **kwargs)
        for field_name in ("message_id", "kind", "message_type", "subtype"):
            self.fields[field_name].disabled = True
