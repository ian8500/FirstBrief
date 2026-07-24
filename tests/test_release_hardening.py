from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client


def test_security_headers_and_csp_safe_shell() -> None:
    response = Client().get("/access/login/")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "object-src 'none'" in response["Content-Security-Policy"]
    assert b"brand-mark" in response.content
    assert b"app.js" in response.content
    assert b"onclick=" not in response.content


@pytest.mark.django_db
def test_release_evidence_command() -> None:
    call_command("release_evidence")
