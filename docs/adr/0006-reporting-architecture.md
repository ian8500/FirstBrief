# ADR 0006: Versioned report catalogue

- Status: Accepted
- Date: 2026-07-23

## Decision

Implement one authorised, site-scoped report framework with versioned catalogue definitions and reusable criteria. Small reports render synchronously; large reports create asynchronous immutable `ReportRun` snapshots and protected exports. CSV neutralises spreadsheet formulas.

## Consequences

Reports F01–F14 and refinements F17–F28 share security, filtering, viewer, export,
and seeded reconciliation infrastructure. User/watch cohorts are explicit
site-scoped reporting references. `ImportChangeRecord` provides the stable input
contract for Prompt 9. Export classification, quotas, expiry, and
re-authentication remain policy decisions requiring approval.
