# ADR 0005: Transactional outbox and idempotent jobs

- Status: Accepted
- Date: 2026-07-23

## Decision

Persist notification and asynchronous-work intent in a PostgreSQL outbox inside the initiating transaction. Workers use stable idempotency/deduplication keys, retries, quiet-hour policy, and visible dead-letter state. Lifecycle workers call domain services rather than updating models directly.

## Consequences

Redis/RabbitMQ or an enterprise scheduler may transport work, but PostgreSQL records authoritative intent/result. Queue outage cannot lose committed work; replay and late-job behaviour must be deterministic.

