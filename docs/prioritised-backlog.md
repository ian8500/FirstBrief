# Prioritised delivery backlog

Each phase is a gate: update traceability, run the stated quality checks, report changed files/results/risks, and obtain authority before beginning the next prompt.

| Order | Prompt/workstream | Depends on | Exit evidence |
|---|---|---|---|
| 0 | Repository assessment and solution design | controlling PDF | complete inventory, design, ADRs, threat/NFR/state models |
| 1 | Engineering foundation | 0 | runnable secure skeleton, CI, PostgreSQL migration, worker abstraction |
| 2 | Identity/authentication/authorisation | 1 | privilege-escalation and scope tests |
| 3 | Configuration taxonomy | 2 | database/service integrity tests |
| 4 | Message core and lifecycle | 2, 3 | state, audience, concurrency, file, audit tests |
| 5 | Scheduling and notifications | 4 | DST, outage, replay, deduplication tests |
| 6 | Dashboard and consumption | 4, 5 | browser acknowledgement/access tests |
| 7 | Search and maintenance | 2, 4 | query performance and cross-site leakage tests |
| 8 | Reporting and compliance | 2, 4, 6, 7 | seeded reconciliation/export tests |
| 9 | SAP import | 2, 3 | contract, hostile parser, preview/commit/reconciliation tests |
| 10 | Audit, retention, continuity | 4, 8, 9 | purge/hold, continuity checksum, restore evidence |
| 11 | Accessibility/security/operations hardening | all features | WCAG, ASVS, scan, load and remediation reports |
| 12 | Full verification/release candidate | all prior gates | clean/upgrade migration, recovery, UAT, complete traceability |

