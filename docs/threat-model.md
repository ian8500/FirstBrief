# Threat model

## Assets and actors

Protected assets include operational instructions/BOTD, personal and organisational data, access configuration, credentials/sessions, PDFs, audit evidence, compliance reports, SAP input, notification contents, backups, and continuity packs. Actors include normal users, supervisors, preparers, authorities/approvers, report viewers, administrators, auditors, integration identities, and unauthorised external or insider threats.

## Principal threats and controls

| Threat | Boundary/asset | Required controls | Verification |
|---|---|---|---|
| Credential stuffing/session theft | identity | SSO/MFA preferred, Argon2 fallback, rate limits, lockout, secure cookies, rotation, CSRF | auth abuse and session tests |
| Privilege escalation | all business data | deny-by-default service policies, site/message-type/audience scope, admin re-authentication | exhaustive negative permission matrix |
| Cross-site inference | counts/search/suggest/export/jobs | scope at query root; no post-filtering; opaque IDs | leakage tests for every channel |
| IDOR/file disclosure | PDFs/exports | opaque object keys, authorised streaming or short-lived signed access, no public bucket | direct-object negative tests |
| Malicious upload | file pipeline | size/type/PDF validation, quarantine, malware scan, checksum, isolated processing | hostile/malformed corpus |
| Lifecycle tampering/races | messages | server-side state machine, transactions, optimistic versioning, idempotency | concurrent and duplicate-job tests |
| Notification divergence/duplication | email | transactional outbox, stable dedup keys, retry/dead-letter controls | outage and replay tests |
| Audit alteration/repudiation | audit | append-only permissions, immutable evidence, actor/context/correlation, restricted export | database-role and tamper tests |
| SAP poisoning/path traversal | import | authenticated landing zone, fixed paths, untrusted content handling, staged preview, transactional exact commit, quarantine | fuzz/property/hostile input tests |
| Formula injection | CSV export | prefix/escape dangerous cells, controlled MIME/download | export payload tests |
| Stored/reflected XSS | content/feedback | template autoescape, sanitisation policy, CSP, safe PDF handling | SAST/DAST and browser tests |
| CSRF/automation | state-changing actions | CSRF tokens, SameSite cookies, rate limits, confirmation/re-authentication | request-forgery tests |
| Excessive retention/data loss | records/backups | approved schedules, legal hold, purge preview/evidence, encrypted tested backups | restore and retention exercises |
| Time manipulation | lifecycle/compliance | UTC storage, approved time sync, IANA zones, DST tests, clock monitoring | fake-clock and drift alert tests |
| Dependency/secrets compromise | supply chain | lockfiles, provenance/scanning, secrets manager, rotation, least privilege | CI scans and rotation exercise |
| Denial of service | reports/imports/login | pagination, quotas, async jobs, timeouts, backpressure, health/queue alerts | load and fault tests |

## Residual-risk decisions

The product owner, security owner, records manager, and operational owner must approve local-auth availability, audience precedence, administrator re-authentication, report/export limits, retention/legal hold, upload policy, SAP trust contract, and recovery targets. High or critical findings block release unless a named risk owner records a time-bounded exception.

