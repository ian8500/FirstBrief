# Role-aware attention inbox

## Purpose

The operational dashboard presents one deterministic, deny-by-default queue of
work relevant to the signed-in user. It combines reading, approval and authorised
operational recovery without broadening any underlying permission.

## Selection and authorisation

| Item | Selection rule | Additional authorisation |
|---|---|---|
| Overdue mandatory | Effective, Mandatory audience right, not cleared | Normal message-type/site/group/audience scope |
| Newly effective | Effective since the login timestamp and not cleared | Normal reader scope |
| Forthcoming | Released pending effective inside configured hours | Normal reader scope |
| Unread BOTD | Current effective BOTD, unread, applicable to default group | Normal reader scope |
| Approval | Draft explicitly assigned to current user | `APPROVE_MESSAGES` plus management site scope |
| Returned draft | Current user is originator; approved message transitioned back to Draft | Management site scope |
| Failed delivery | Dead notification job for a message in management scope | `MANAGE_MESSAGES` |
| Expiring instruction | Effective Instruction expiring inside personal review window | `MANAGE_MESSAGES` |
| Continue reading | Previously opened, not cleared, still accessible | Normal reader scope |

The service checks capability before executing administrator/approver queries.
Counts are calculated only from the resulting authorised set. Preferences can
remove categories but cannot add permission.

## Ordering and query behaviour

Items are sorted by:

1. urgency rank;
2. relevant time;
3. case-insensitive Message ID;
4. category and stable item key.

Messages, versions, audience rights and receipts are materialised in bounded
queries. Management categories use scoped querysets with `select_related` and
`prefetch_related`; returned-history evidence and receipts are loaded in bulk.
`tests/test_operations.py::test_attention_query_count_does_not_grow_per_message`
guards against per-row query growth.

## Verification record

On 24 July 2026:

- Ruff, mypy, migration drift and the production deployment check passed.
- The full suite passed: 124 tests passed and 4 were skipped.
- Coverage was 85.50%, above the 80% gate.
- Browser checks passed at 1280, 768 and 390 px with no page/task overflow or
  console warnings.
- Release evidence reported ready.
- The exact isolated `pip-audit --requirement requirements/base.txt` remained
  inconclusive because the environment stalled while bootstrapping its temporary
  pip environment. The supplementary direct pinned audit reported no known
  vulnerabilities; it is not equivalent to a transitive dependency audit.

## User guide

Open **Dashboard** and use **Requires your attention** from top to bottom.
Every row states:

- an urgency label in text and a non-colour symbol;
- the Message ID and title;
- why it appears;
- the relevant time; and
- the action currently permitted.

If a recently opened message remains uncleared, **Continue reading** appears
above the inbox. Selecting a task displays an “Opening task…” status while the
next page loads.

Use **Customise dashboard** to choose optional categories, the maximum number of
items and the expiring-instruction window. Mandatory uncleared work is always
shown. Preferences are saved against the user account and apply on other devices.

If an optional administrative data source is unavailable, the dashboard keeps
reader tasks usable and displays a degraded-state explanation. An empty inbox
states that the user is up to date and links to Mandatory Messages.

## Accessibility and responsive behaviour

- The queue is an ordered list with a labelled section and semantic headings.
- Urgency never relies on colour alone.
- Status/loading/degraded messages use appropriate live/status semantics.
- Every action is a normal keyboard-focusable link.
- At tablet/mobile widths actions move beneath their task content without
  horizontal page overflow.
