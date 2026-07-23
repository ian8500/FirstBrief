# FirstBrief solution design

## Decision summary

FirstBrief will be a modular Django monolith with explicit domain services, PostgreSQL as the system of record, protected object storage for files, and an outbox-backed worker for time-based and asynchronous work. Server-rendered HTML with progressive enhancement keeps core workflows accessible without making browser JavaScript an authority boundary.

The system stores timestamps in UTC and renders them in a configured site timezone. Authorisation, audience resolution, lifecycle transitions, and audit creation occur in service-layer transactions. Views, APIs, commands, and workers call the same services.

## Context and trust boundaries

Users enter through a TLS reverse proxy and authenticate through corporate OIDC/SAML where configured. A controlled local-account provider is a fallback. Application instances access PostgreSQL, the job broker, protected object storage, an email adapter, malware scanning, and the SAP landing zone through least-privilege service identities. Files are streamed through authorised application endpoints or short-lived signed URLs, never predictable public URLs.

## Bounded modules

| Module | Responsibilities | Public service surface |
|---|---|---|
| Identity and access | users, roles, granular permissions, sessions, supervisors, site scope | authenticate, authorise, resolve scope, manage local credentials |
| Configuration | sites, PMGs, message group types/groups, message types/subtypes, sectors, distributions | create/update taxonomy, validate exclusivity, protect referenced records |
| Messaging | BOTD and instruction aggregates, versions, files, audience rights | draft, validate, version, attach, resolve audience |
| Lifecycle | approval, release, effective, expiry, archive, withdrawal, cancellation, supersession | transition with expected version and idempotency key |
| Consumption | dashboard projections, access sessions, viewing time, acknowledgement, print/email-to-self, feedback | list scoped work, record access/evidence |
| Notifications | outbox, templates, quiet hours, retry, deduplication, dead letters | enqueue transactionally, deliver, replay |
| Reporting | catalogue, criteria, snapshots, asynchronous generation, controlled export | authorise criteria, generate, download |
| Import | SAP contract, landing, parse, validate, preview, commit, reconcile, quarantine | stage, preview, commit exact staged version |
| Audit and retention | append-only events, audit viewer, legal holds, purge evidence, continuity export | record, query by policy, retain/purge/export |

Cross-module calls use typed service inputs and stable identifiers. Modules do not import another module’s persistence internals. Database foreign keys enforce necessary referential integrity inside the same deployment.

## Request and background execution

1. The edge assigns or validates a correlation ID.
2. Authentication establishes user, site, and delegated/impersonation context.
3. The application service authorises the action and loads the aggregate with scope constraints.
4. A transaction validates state and optimistic version, persists changes, appends audit events, and writes outbox records.
5. After commit, workers claim outbox/job records using database locking.
6. Delivery/state jobs call the same domain services with idempotency keys; retries cannot duplicate effects.

## Data and file strategy

PostgreSQL holds authoritative relational data, immutable message versions, audit metadata, outbox state, import batches, and report job metadata. Object storage holds opaque file keys, checksums, scan state, classification, and version metadata. Uploads remain quarantined until type, size, PDF integrity, checksum, filename policy, and malware scan pass.

## Interface strategy

- HTML is the primary interface; HTMX/Alpine may progressively enhance bounded interactions.
- Django REST Framework is limited to documented integrations and interactive components that need JSON.
- Every list, count, suggestion, export, file retrieval, and worker query starts from an authorised scope.
- Date/time fields expose timezone context and reject ambiguous or nonexistent local times unless a deterministic policy is configured.
- Status uses text/icon cues in addition to colour.

## Environments and operations

Development, test, staging, and production use environment-based configuration and separate credentials/data. Containers provide repeatable application and worker processes. Health checks distinguish liveness from readiness. Structured logs, metrics, traces, queue age, outbox/dead-letter counts, transition lag, import failures, and audit anomalies feed alerts. Secrets are supplied by an approved secrets manager.

## Verification architecture

- Domain tests: state transitions, audience precedence, date policy, idempotency, password/reset policy.
- PostgreSQL integration tests: constraints, transactions, outbox, imports, report reconciliation.
- Permission tests: every endpoint, query, count, suggestion, file, export, and background action.
- Browser tests: login, dashboard, reading/clearance, authoring/approval, withdrawal/cancellation, admin, reporting.
- Release gates: WCAG 2.2 AA evidence, security scanning, recovery exercise, performance results, complete traceability.

## Open decisions

The items listed under “Decisions that need owner approval” in the requirements review block production acceptance. Safe defaults may be implemented behind configuration, but operational/security/retention scope will not be guessed.

