from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError

from firstbrief.identity.models import IdentityPolicy


class FirstBriefPasswordValidator:
    def validate(self, password: str, user: Any | None = None) -> None:
        policy = IdentityPolicy.load()
        errors: list[str] = []
        if len(password) < policy.password_min_length:
            errors.append(f"Use at least {policy.password_min_length} characters.")
        if len(password) > policy.password_max_length:
            errors.append(f"Use no more than {policy.password_max_length} characters.")
        categories = (
            bool(re.search(r"[a-z]", password)),
            bool(re.search(r"[A-Z]", password)),
            bool(re.search(r"\d", password)),
            bool(re.search(r"[^A-Za-z0-9]", password)),
        )
        if sum(categories) < 3:
            errors.append("Use at least three of lowercase, uppercase, numbers and symbols.")
        if user:
            lowered = password.casefold()
            for attribute in ("username", "first_name", "last_name"):
                value = str(getattr(user, attribute, "")).strip().casefold()
                if len(value) >= 3 and value in lowered:
                    errors.append("Do not include your user ID or name.")
                    break
        if errors:
            raise ValidationError(errors)

    def get_help_text(self) -> str:
        return (
            "Use 12-128 characters, at least three character categories, "
            "and do not include your user ID or name."
        )
