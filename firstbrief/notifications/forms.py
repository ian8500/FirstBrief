from typing import ClassVar

from django import forms

from firstbrief.notifications.models import NotificationPolicy


class NotificationPolicyForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = NotificationPolicy
        fields = (
            "creation_anchor",
            "creation_offset_minutes",
            "approval_anchor",
            "approval_offset_minutes",
            "quiet_hours_start",
            "quiet_hours_end",
            "timezone_name",
            "maximum_attempts",
            "retry_delay_minutes",
            "archive_retention_days",
        )
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "quiet_hours_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_hours_end": forms.TimeInput(attrs={"type": "time"}),
        }
