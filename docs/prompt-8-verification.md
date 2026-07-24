# Prompt 8 verification

## Delivered

- Versioned F01–F14 report catalogue and reusable, authorised criteria.
- Site, PMG, associated-group, cohort, sector, role, user, message, batch,
  access-cohort, period, archive and future filters.
- Include-in-report exclusion and Prohibited-right precedence.
- Synchronous small results and Celery-backed immutable background snapshots.
- Print-friendly retained viewer with Close-to-criteria behaviour.
- Protected, audited PDF and CSV exports with spreadsheet-formula protection.
- Site-scoped user/watch cohorts and the Prompt 9 import-change contract.

## Automated evidence

`tests/test_reporting.py` reconciles all fourteen catalogue builders against a
seeded dataset. It additionally covers period filters, capability and owner
isolation, queued execution, private downloads, PDF rendering, CSV formula
neutralisation and Include in Report exclusion.

## Manual evidence

The catalogue, reusable criteria, status viewer, empty-result handling, Close
link, print action and download actions are exercised through the local
authenticated application. Final cross-browser/WCAG evidence remains Prompt 11.

## Deferred policy

Export expiry, quotas, classification markings and re-authentication are not
invented by this prompt. They remain policy decisions documented in ADR 0006.
