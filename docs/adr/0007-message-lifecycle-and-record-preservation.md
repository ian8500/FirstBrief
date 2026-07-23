# ADR 0007: Message lifecycle and record preservation

- Status: Accepted
- Date: 2026-07-23

## Context

The source requirements define BOTD and Instruction authoring, approvals, timed
visibility and archive behaviour. The implementation blueprint adds proposed
withdrawal, cancellation and supersession rules. Operational evidence must not be
lost when a message is corrected or removed from view.

## Decision

Use one stable `Message` aggregate with immutable `MessageVersion` records and an
append-only status history. Commands use a caller-supplied expected aggregate
version and idempotency key. Audience rights resolve in the order `Prohibited`,
`Mandatory`, then `Allowed`.

The formal states are Draft / Unapproved, Approved Pending Release, Released
Pending Effective, Effective, Expired, Archived, Withdrawn and Cancelled.
Withdrawal is permitted before effective time; cancellation is permitted after
release, including Released Pending Effective; supersession creates a bidirectional
link without changing or deleting the original.

Physical deletion is not exposed by the application. “Delete” behaviour in the
legacy BOTD requirement is implemented as withdrawal/archive so the record, its
versions and audit evidence remain available. This is a deliberate safety
interpretation pending records-policy confirmation.

Display and Print PDFs remain quarantined until structural validation, checksum
creation and malware scanning succeed. Storage keys are opaque and user filenames
are retained only as metadata. Filename matching is configurable.

## Consequences

- Stale edits fail and must be retried against the current aggregate version.
- Reusing an idempotency key for another command is rejected.
- Approval records both the decision justification and any subtype-validity
  exception.
- The proposed FR-K01, FR-K02 and FR-K03 behaviours are implemented but remain
  marked Proposed in traceability until formal product and records approval.
- A later scheduler can call the same lifecycle commands without bypassing domain
  validation.
