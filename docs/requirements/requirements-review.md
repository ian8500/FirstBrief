# Requirements review

## Coverage result

All 52 pages were processed. The register contains 121 unique detailed requirements: 69 operational/functional requirements and 52 administration/configuration requirements. No detailed ID is duplicated. Every record contains its theme, role, need, outcome, source reference, acceptance criteria, and detailed source page(s).

## Material findings

1. **Dependencies are unusable as supplied.** All 121 requirements say `None`, although identity, taxonomy, lifecycle, audience rights, notifications, and reports have obvious sequencing dependencies. The prioritised backlog supplies delivery dependencies without rewriting the source.
2. **Ownership is unresolved.** Every requirement owner is `TBD`. Product, security, records-management, reporting, SAP integration, and operational owners must be named before acceptance.
3. **Authentication controls conflict with current practice.** FR-A02 requires an emailed temporary password and FR-A03 describes a maximum password length of 14. The safer business-equivalent decision is SSO/MFA where available and single-use reset links plus Argon2 local fallback with a minimum length and no low artificial maximum.
4. **Lifecycle vocabulary is incomplete.** Release, effective, expiry, archive, unapproval, withdrawal, cancellation, and supersession need a formal transactional state machine. The source does not fully define late jobs, concurrent edits, DST, or notification timing.
5. **Audience precedence is ambiguous.** A user may obtain contradictory Mandatory, Allowed, or Prohibited rights through multiple groups. `Prohibited > Mandatory > Allowed > no access` is proposed, but product/security approval is required.
6. **Viewing time is not proof of reading.** FR-D05/D06 require duration and clear/read behaviour. The system will label passive timing as cumulative foreground viewing time; explicit acknowledgement is the compliance event.
7. **Reporting wording is repetitive and underspecified.** Fourteen records cite `User Guide Sec 11.x`; export limits, asynchronous thresholds, reconciliation rules, and formula-injection protection are absent.
8. **SAP import lacks a contract.** Encoding, schema version, identity keys, source authentication, duplicate policy, preview/commit equivalence, quarantine, rollback, and reconciliation must be agreed before production.
9. **Non-functional acceptance targets are absent.** Availability, RTO/RPO, load profile, recovery, browser support, retention, file limits, malware scanning, accessibility evidence, and support hours require measurable approval.
10. **Site scoping must cover indirect channels.** Counts, autocomplete, exports, files, background tasks, and audit viewers must apply the same service/query policies as screens.

## Potential overlaps, not duplicates

- FR-A03, FR-H02, and FR-G2-06 all address password policy/change flows.
- FR-A04, FR-I01, FR-I02, FR-G2-31, and FR-G2-34 overlap in role/site/message-type scope.
- FR-E03, FR-E27, FR-E28, and FR-G2-14/15/16 overlap in lifecycle and notification scheduling.
- FR-E07 and FR-G2-20/21 overlap in audit/retention assurance.
- FR-F01–F14 and FR-F17–F28 share a common report framework and should not become independent one-off implementations.

## Decisions that need owner approval

- Audience-right precedence and the meaning of exclusive membership.
- Authoritative site timezone and behaviour for DST gaps/overlaps.
- Whether a released-but-not-effective instruction is visible and withdrawable.
- Retention periods, legal holds, purge approval, and audit retention.
- Local authentication availability when SSO is deployed.
- SAP schema, source trust, identity key, and conflict/rollback policy.
- File size/type limits, malware-scanning service, and PDF filename enforcement.
- Report data-classification, maximum export size, and re-authentication rules.
- Whether supervisors may ever acknowledge on another user’s behalf.

## Proposed requirements status

NFR-01–NFR-10 and FR-K01–FR-K07 from the implementation guide are retained as **proposed** requirements. They are necessary to close material gaps but are not represented as contractual source requirements until formally approved.
