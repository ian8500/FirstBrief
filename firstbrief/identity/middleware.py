from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from firstbrief.identity.models import IdentityPolicy


class IdentitySessionMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            request.session.set_expiry(IdentityPolicy.load().session_timeout_minutes * 60)
            allowed = {
                reverse("identity:password-change"),
                reverse("identity:logout"),
                reverse("health-live"),
                reverse("health-ready"),
            }
            if request.user.must_change_password and request.path not in allowed:
                return redirect("identity:password-change")
        return self.get_response(request)
