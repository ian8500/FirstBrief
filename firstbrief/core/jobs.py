"""Background-job dispatch abstraction.

Business jobs are added by later prompts. Callers depend on this interface rather
than importing Celery directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from celery import current_app


@dataclass(frozen=True, slots=True)
class JobRequest:
    task_name: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    run_at: datetime | None = None
    queue: str = "default"

    def __post_init__(self) -> None:
        if not self.task_name:
            raise ValueError("task_name is required")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required")


class JobDispatcher(Protocol):
    def enqueue(self, request: JobRequest) -> str: ...


class CeleryJobDispatcher:
    def enqueue(self, request: JobRequest) -> str:
        result = current_app.send_task(
            request.task_name,
            kwargs=request.payload,
            eta=request.run_at,
            queue=request.queue,
            headers={"idempotency_key": request.idempotency_key},
        )
        return str(result.id)
