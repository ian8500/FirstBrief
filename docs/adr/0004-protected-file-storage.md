# ADR 0004: Quarantined, protected file storage

- Status: Accepted
- Date: 2026-07-23

## Decision

Store files by opaque object key in approved protected storage. Quarantine uploads until type/size/PDF-integrity, checksum, filename-policy, and malware checks pass. Retrieve only after application authorisation, using controlled streaming or short-lived signed access.

## Consequences

Predictable public URLs and user-supplied storage paths are prohibited. Scan failures, storage outage, version retention, range requests, backup/restore, and continuity export need tested adapter behaviour.

