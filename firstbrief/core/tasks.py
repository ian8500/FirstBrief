"""Non-business worker diagnostics."""

from __future__ import annotations

from typing import Any

from celery import shared_task


@shared_task(name="firstbrief.core.worker_ping")  # type: ignore[untyped-decorator]
def worker_ping() -> dict[str, Any]:
    return {"status": "ok"}
