# ADR 0006: Versioned report catalogue

- Status: Accepted
- Date: 2026-07-23

## Decision

Implement one authorised, site-scoped report framework with versioned catalogue definitions and reusable criteria. Small reports may render synchronously; large reports create asynchronous `ReportRun` snapshots and protected expiring exports. CSV neutralises spreadsheet formulas.

## Consequences

Reports F01–F14 and F17–F28 share security, filtering, viewer, export, and reconciliation infrastructure. Report-specific query logic still needs seeded expected-result tests. Export classification, quotas, expiry, and re-authentication require approval.

