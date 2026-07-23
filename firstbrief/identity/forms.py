from __future__ import annotations

from typing import ClassVar, cast

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm

from firstbrief.identity.models import User


class AccessibleAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="User ID",
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class LocalPasswordChangeForm(PasswordChangeForm):
    def save(self, commit: bool = True) -> User:
        user = cast(User, super().save(commit=False))
        user.must_change_password = False
        from django.utils import timezone

        user.password_changed_at = timezone.now()
        if commit:
            user.save(update_fields=("password", "must_change_password", "password_changed_at"))
        return user


class LocalResetConfirmForm(SetPasswordForm):  # type: ignore[type-arg]
    def save(self, commit: bool = True) -> User:
        user = cast(User, super().save(commit=False))
        user.must_change_password = False
        user.failed_login_count = 0
        user.locked_until = None
        from django.utils import timezone

        user.password_changed_at = timezone.now()
        if commit:
            user.save(
                update_fields=(
                    "password",
                    "must_change_password",
                    "failed_login_count",
                    "locked_until",
                    "password_changed_at",
                )
            )
        return user


class UserCreateForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "site",
            "roles",
            "message_groups",
            "default_message_group",
            "include_in_reports",
            "imported_from_sap",
        )
        widgets: ClassVar[dict[str, object]] = {
            "roles": forms.CheckboxSelectMultiple,
            "message_groups": forms.CheckboxSelectMultiple,
        }

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        default = cleaned.get("default_message_group")
        groups = cleaned.get("message_groups")
        if default and groups is not None and default not in groups:
            self.add_error(
                "default_message_group",
                "Default group must be one of the memberships.",
            )
        return cleaned
