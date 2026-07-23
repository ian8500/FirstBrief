# Domain model

## Aggregate boundaries

### Identity

`User` belongs to a `Site`, may hold `Role` assignments, `Permission` grants, group memberships, a validated default group, message-type access, `SupervisorRelationship` records, and an `IncludeInReports` flag. `Role` bundles permissions but does not bypass site or audience scope. Delegation is time bounded and audited.

### Configuration

`PrimaryMessageGroup` contains hierarchical `MessageGroup` nodes. `MessageGroupType` is
independently hierarchical, controls allowed message types, and may enforce exclusive
user membership. `MessageType` owns content, display, approval, search, subtype and
effective-date behaviour. `MessageSubType` is scoped by primary group and message type
and owns validity bounds. `Sector` and `EmailDistribution` provide audience and
notification dimensions. Referenced configuration is deletion-protected.

### Message

`Message` is the stable identity and current lifecycle pointer. `MessageVersion` is immutable after approval and contains title, summary/content, dates, taxonomy, and optimistic version. `FileAsset` references an opaque stored object, checksum, scan outcome, media metadata, and version. `MessageAudienceRight` grants `Mandatory`, `Allowed`, or `Prohibited` rights to scoped subjects. `Approval` records decision, actor, reason, and version.

`BOTD` and `Instruction` share lifecycle/value objects where semantics match, but remain distinct domain types so their different fields and workflows are explicit.

### Consumption

`MessageAccessEvent` records an authorised open. `ViewingSession` accumulates foreground intervals subject to idle thresholds. `Acknowledgement` is the compliance event and is unique per user/message/version unless policy explicitly says otherwise. `PrintEvent`, `EmailEvent`, and `Feedback` are separate auditable records.

### Jobs and notifications

`OutboxEvent` is written in the initiating transaction. `NotificationJob` contains a stable deduplication key, schedule, attempts, quiet-hour adjustment, and terminal/dead-letter state. `LifecycleJob` invokes a domain transition with an idempotency key and expected target time.

### Reporting, import, and assurance

`ReportDefinition` identifies a versioned catalogue report; `ReportRun` stores authorised criteria, requester scope snapshot, status, expiry, and export asset. `ImportBatch` owns immutable staged input, parsed `ImportChange` records, preview selection, commit outcome, and reconciliation. `AuditEvent` is append-only and contains actor/context, correlation ID, object/version, action, reason, and before/after diff. `LegalHold` prevents governed purge. `PurgeRun` records preview, approval, result, and evidence.

## Key invariants

- A user can access only records inside resolved site/message-type/audience scope.
- Default group must be one of the user’s current eligible groups.
- A user may belong to at most one group for each exclusive message-group type.
- Message-group and group-type parentage must be acyclic; message-group parents share a PMG.
- Message subtype maximum validity is never less than minimum validity.
- Audience resolution is deterministic; proposed precedence is `Prohibited > Mandatory > Allowed`.
- An approved message version is immutable; edits create a new draft/version.
- Every lifecycle transition is validated, transactional, idempotent, concurrency checked, and audited.
- Release, effective, expiry, and archive timestamps are ordered under the approved policy.
- Acknowledgement cannot be inferred from elapsed viewing time.
- Outbox and business changes commit together.
- Import commit applies the exact reviewed staged version or fails.
- Files cannot be served until authorised and scan-valid.
- Audit records cannot be updated or deleted by application roles.
- Legal hold overrides normal retention/purge.

## Planned persistence namespaces

`identity`, `configuration`, `messaging`, `consumption`, `notifications`, `reporting`, `imports`, and `assurance` are Django apps. Models may share one PostgreSQL database, but service interfaces and tests enforce module ownership.
