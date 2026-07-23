# Prompt 5 verification

## Delivered

- Transactional `OutboxEvent` records written alongside message creation and
  approval.
- Database-authoritative lifecycle schedules for release, effective, expiry,
  archive, retention review and unapproved-at-effective alerts.
- Idempotent late-job catch-up using the Prompt 4 domain state machine.
- Configurable event/release/effective notification anchors, signed offsets,
  IANA-timezone quiet hours, retry limits and retry delay.
- Deduplicated notification jobs, bounded exponential retry, dead-letter state,
  audit evidence and authorised manual resend.
- Celery tasks and one-minute Beat entries for outbox processing, lifecycle
  transitions and notification delivery.
- Accessible notification operations page for policy management, recent delivery
  status and dead-letter visibility.

## Verification

The Prompt 5 tests exercise:

- transaction rollback and outbox consistency;
- creation and approval recipient routing;
- duplicate outbox and lifecycle execution;
- worker-outage catch-up through release, expiry and archive;
- unapproved-at-effective policy alerts;
- quiet hours across the Europe/London DST boundary;
- retry, dead-letter and manual resend behaviour;
- revision rescheduling and stale-job cancellation;
- Celery entry points and permission-protected operations UI.

Run the repository-equivalent CI gates:

```bash
ruff format --check .
ruff check .
mypy firstbrief tests tools
pytest --cov=firstbrief --cov-report=term-missing
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Retention boundary

Prompt 5 schedules and audits retention-review eligibility. It does not physically
purge a message. Prompt 10 supplies legal holds, purge preview/approval and purge
evidence before destructive retention enforcement is enabled.
