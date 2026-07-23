# ADR 0005: Transactional outbox and idempotent jobs

- Status: Accepted
- Date: 2026-07-23

## Decision

Persist notification and asynchronous-work intent in a PostgreSQL outbox inside the initiating transaction. Workers use stable idempotency/deduplication keys, retries, quiet-hour policy, and visible dead-letter state. Lifecycle workers call domain services rather than updating models directly.

Message creation and approval append notification intent in the same transaction
as the business change. Database-backed lifecycle jobs schedule release,
effective, expiry, archive, retention review and unapproved-at-effective checks.
Celery Beat wakes stateless workers every minute; the database remains the
authoritative schedule and supports deterministic catch-up after an outage.

Retention jobs create auditable review-due evidence. Destructive purge remains
deferred until Prompt 10 adds legal-hold and purge-approval controls.

## Consequences

Redis/RabbitMQ or an enterprise scheduler may transport work, but PostgreSQL records authoritative intent/result. Queue outage cannot lose committed work; replay and late-job behaviour must be deterministic.

Notification visibility and email timing are independent. Creation and approval
delivery can anchor to event, release or effective time with signed offsets.
Quiet hours are evaluated in an IANA timezone, retries use bounded exponential
backoff, and exhausted work remains visible for authorised manual recovery.
