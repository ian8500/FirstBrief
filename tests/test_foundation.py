from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import Mock, patch

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from firstbrief.core.jobs import CeleryJobDispatcher, JobRequest
from firstbrief.core.logging import JsonFormatter
from firstbrief.core.models import SystemSetting
from firstbrief.core.tasks import worker_ping
from firstbrief.identity.models import User


@pytest.mark.django_db
def test_home_is_accessible(client: Client) -> None:
    user = User.objects.create_user(username="foundation-user", password="Safe-test-42!")
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="#main-content"' in content
    assert 'id="main-content"' in content
    assert "Your briefings" in content


def test_liveness_has_no_cache_and_correlation_id(client: Client) -> None:
    response = client.get("/health/live/", HTTP_X_REQUEST_ID="test-request-123")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
    assert response["Cache-Control"] == "max-age=0, no-cache, no-store, must-revalidate, private"
    assert response["X-Request-ID"] == "test-request-123"


@pytest.mark.django_db
def test_readiness_checks_database(client: Client) -> None:
    response = client.get("/health/ready/")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok"}


def test_readiness_reports_database_failure(client: Client) -> None:
    with patch(
        "firstbrief.core.views.connection.cursor",
        side_effect=RuntimeError("database unavailable"),
    ):
        response = client.get("/health/ready/")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "failed"},
    }


def test_invalid_correlation_id_is_replaced(client: Client) -> None:
    response = client.get("/health/live/", HTTP_X_REQUEST_ID="invalid value\r\nx")
    correlation_id = response["X-Request-ID"]
    assert correlation_id != "invalid value\r\nx"
    assert len(correlation_id) == 36


def test_baseline_security_headers(client: Client) -> None:
    response = client.get("/")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response["Content-Security-Policy"]
    assert response["Permissions-Policy"].startswith("camera=()")
    assert response["Cross-Origin-Resource-Policy"] == "same-origin"


def test_json_404_contains_correlation_reference(client: Client) -> None:
    response = client.get(
        "/missing/",
        HTTP_ACCEPT="application/json",
        HTTP_X_REQUEST_ID="missing-test",
    )
    assert response.status_code == 404
    assert response.json()["correlation_id"] == "missing-test"


@pytest.mark.django_db
def test_system_setting_rejects_secret_keys() -> None:
    setting = SystemSetting(key="api-token", value="unsafe")
    with pytest.raises(ValidationError, match="secrets manager"):
        setting.full_clean()


@pytest.mark.django_db
def test_system_setting_accepts_non_secret_configuration() -> None:
    setting = SystemSetting(key="site-timezone", value="Europe/London")
    setting.full_clean()
    setting.save()
    assert str(setting) == "site-timezone"


def test_development_seed_is_refused_in_test_environment() -> None:
    with pytest.raises(CommandError, match="only be loaded in development"):
        call_command("seed_development")


def test_job_request_requires_idempotency_key() -> None:
    with pytest.raises(ValueError, match="idempotency_key"):
        JobRequest(task_name="example.task")


def test_job_request_requires_task_name() -> None:
    with pytest.raises(ValueError, match="task_name"):
        JobRequest(task_name="", idempotency_key="key")


def test_celery_dispatcher_preserves_idempotency_metadata() -> None:
    async_result = Mock(id="job-123")
    request = JobRequest(
        task_name="example.task",
        payload={"record_id": 42},
        idempotency_key="record-42-v1",
    )
    with patch("firstbrief.core.jobs.current_app.send_task", return_value=async_result) as send:
        job_id = CeleryJobDispatcher().enqueue(request)
    assert job_id == "job-123"
    send.assert_called_once_with(
        "example.task",
        kwargs={"record_id": 42},
        eta=None,
        queue="default",
        headers={"idempotency_key": "record-42-v1"},
    )


def test_worker_ping_has_no_business_side_effects() -> None:
    assert worker_ping.run() == {"status": "ok"}


def test_json_formatter_emits_stable_schema() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="firstbrief.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    parsed: dict[str, Any] = json.loads(formatter.format(record))
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "firstbrief.test"
    assert parsed["message"] == "hello"
    assert "timestamp" in parsed
    assert "correlation_id" in parsed
