"""Foundation views and health probes."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "home.html")


@never_cache
@require_GET
def liveness(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "status": "alive",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


@never_cache
@require_GET
def readiness(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("readiness_check_failed", extra={"event": "readiness_check_failed"})
        return JsonResponse(
            {"status": "not_ready", "checks": {"database": "failed"}},
            status=503,
        )
    return JsonResponse(
        {
            "status": "ready",
            "checks": {"database": "ok"},
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
