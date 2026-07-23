# Message lifecycle state machine

## States

`DRAFT`, `APPROVED_PENDING_RELEASE`, `RELEASED_PENDING_EFFECTIVE`, `EFFECTIVE`, `EXPIRED`, `ARCHIVED`, `WITHDRAWN`, and `CANCELLED`.

`SUPERSEDED` is represented by an explicit bidirectional relationship plus the original lifecycle state; it is not a transition that erases history.

## Transitions

| From | Command | To | Principal conditions |
|---|---|---|---|
| Draft | submit/approve | Approved pending release | valid content/audience/dates/files; approval permission |
| Approved pending release | unapprove | Draft | before release; policy permits |
| Approved pending release | release | Released pending effective or Effective | due; idempotent scheduler/manual authority |
| Approved pending release | withdraw | Withdrawn | before effective; reason required |
| Released pending effective | become effective | Effective | due; not withdrawn; idempotent |
| Released pending effective | withdraw | Withdrawn | before effective; reason and authority |
| Released pending effective | cancel | Cancelled | post-release safety action; reason and authority |
| Effective | expire | Expired | due; idempotent |
| Effective | cancel | Cancelled | reason and authority; original retained |
| Effective | supersede | Effective plus link | replacement approved/effective under policy |
| Expired | archive | Archived | retention/archive threshold reached |
| Cancelled | archive | Archived | retention/archive threshold reached |
| Withdrawn | archive | Archived | retention/archive threshold reached |

When effective time has already arrived at release, release moves directly to
`EFFECTIVE`. Cancellation from Released Pending Effective is implemented as the
FR-K02 proposed post-release safety action and remains subject to formal product
approval.

## Transition contract

Every command includes actor/context, message ID, expected aggregate version, effective command time, correlation ID, and idempotency key. The service:

1. locks or version-checks the aggregate;
2. recomputes authorisation and site scope;
3. validates source state, dates, and policy;
4. creates the next immutable version/status record;
5. appends an audit event and transactional outbox records;
6. commits once.

Repeated commands with the same idempotency key return the recorded result. A stale expected version fails with a refresh/compare response. Workers never write lifecycle fields directly.

## Time policy

Timestamps are stored in UTC. Users enter and view time in a configured IANA site timezone. Ambiguous/nonexistent local times are rejected with an explanatory validation message unless an approved fold/gap policy is configured. Late jobs perform every still-valid missed transition in order and emit one deduplicated notification per policy.

## Visibility and evidence

Visibility is derived from lifecycle, audience resolution, message-type configuration, and site scope. Notification timing is separate from visibility. Withdrawal/cancellation produces an immutable banner/reason and configured notifications. Viewing sessions and acknowledgement remain separate evidence.
