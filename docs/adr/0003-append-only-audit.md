# ADR 0003: Append-only audit

- Status: Accepted
- Date: 2026-07-23

## Decision

Business services append audit events in the same transaction as governed changes. Events include actor, delegation/impersonation context, UTC timestamp, correlation ID, object/version, action, reason, and before/after diff. Application roles cannot update or delete them.

## Consequences

Audit capture cannot be an optional view concern. Database permissions, retention/legal hold, sensitive-field redaction, export authorisation, and operational monitoring require explicit implementation and tests.

