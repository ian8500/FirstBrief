from typing import ClassVar

from django import forms

from firstbrief.operations.models import DashboardPreference, OperationalPolicy


class CloseMessageForm(forms.Form):
    class Action:
        READ = "read"
        CLEAR = "clear"

    action = forms.ChoiceField(
        choices=(
            (Action.READ, "Mark as read — keep in Mandatory Messages"),
            (Action.CLEAR, "Acknowledge and clear — move to Other Messages"),
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


class DashboardPreferenceForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = DashboardPreference
        fields = (
            "show_forthcoming",
            "show_botd",
            "show_approvals",
            "show_returned_drafts",
            "show_notification_failures",
            "show_expiring_instructions",
            "show_recently_opened",
            "item_limit",
            "expiring_within_days",
        )
        labels: ClassVar[dict[str, str]] = {
            "show_botd": "Show unread Briefs of the Day",
            "show_approvals": "Show messages awaiting my approval",
            "show_returned_drafts": "Show my drafts returned for amendment",
            "show_notification_failures": "Show notification failures I can manage",
            "show_expiring_instructions": "Show expiring instructions I can manage",
            "show_recently_opened": "Show recently opened messages not cleared",
            "item_limit": "Maximum attention items",
        }
