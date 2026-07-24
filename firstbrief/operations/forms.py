from typing import ClassVar

from django import forms

from firstbrief.operations.models import OperationalPolicy


class CloseMessageForm(forms.Form):
    class Action:
        READ = "read"
        CLEAR = "clear"

    action = forms.ChoiceField(
        choices=(
            (Action.READ, "Read — keep in Mandatory Messages"),
            (Action.CLEAR, "Read & Clear — move to Other Messages"),
        ),
        widget=forms.RadioSelect,
    )
    view_session = forms.UUIDField(widget=forms.HiddenInput)
    active_seconds = forms.IntegerField(
        min_value=0,
        max_value=14_400,
        widget=forms.HiddenInput,
        initial=0,
    )


class OtherMessageCloseForm(forms.Form):
    view_session = forms.UUIDField(widget=forms.HiddenInput)
    active_seconds = forms.IntegerField(
        min_value=0,
        max_value=14_400,
        widget=forms.HiddenInput,
        initial=0,
    )


class FeedbackForm(forms.Form):
    subject = forms.CharField(max_length=160)
    body = forms.CharField(max_length=4000, widget=forms.Textarea)


class OperationalPolicyForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = OperationalPolicy
        fields = (
            "pre_effective_hours",
            "pre_effective_colour",
            "idle_timeout_seconds",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "pre_effective_colour": forms.TextInput(
                attrs={"type": "color", "class": "colour-input"}
            ),
        }
