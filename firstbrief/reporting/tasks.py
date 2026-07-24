"""Background report generation."""

from celery import shared_task

from firstbrief.reporting.models import ReportRun
from firstbrief.reporting.services import execute_queued_report


@shared_task(  # type: ignore[untyped-decorator]
    autoretry_for=(Exception,), retry_backoff=True, max_retries=3
)
def generate_report(run_id: str) -> None:
    run = ReportRun.objects.select_related("actor").get(pk=run_id)
    if run.status == ReportRun.Status.COMPLETE:
        return
    execute_queued_report(run)
