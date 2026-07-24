# Prompt 6 verification

## Delivered

- Role-aware operational dashboard with permitted navigation, newly effective
  mandatory items, configurable forthcoming window/status and current BOTD.
- Site, role, message-type and group-scoped audience resolution with Prohibited
  precedence over Allowed or Mandatory.
- Sortable Mandatory and Other Message lists, subtype grouping, unread counts and
  text/icon alternatives for unread, overdue and forthcoming states.
- Full-width text/PDF viewer with protected same-origin PDF streaming and private
  no-store caching.
- Read versus Read & Clear workflow, cumulative foreground viewing duration,
  server-side duration caps, idle detection and replay protection.
- Audited print, email-to-self, feedback, open, read and clearance events.
- Effective-since-previous-login behaviour that does not remove already read or
  cleared messages.
- Logout confirmation populated from messages accessed in the browser session.
- Administrator-configurable pre-effective hours/colour and idle timeout.

## Security and interpretation decisions

- Viewing time is supporting evidence; Read & Clear is the compliance action.
- Instruction email contains an authenticated secure link, not a protected PDF
  attachment.
- Unreleased content outside the pre-effective window and prohibited/cross-site
  content are rejected by server-side query services.
- Access evidence is append-only. Mutable receipts hold the current per-user
  reading state.

See ADR 0008 for the full rationale.

## Automated evidence

`tests/test_operations.py` covers:

- role, type, group, site and Prohibited audience boundaries;
- effective-since-login even after Read & Clear;
- default-group BOTD and forthcoming-window behaviour;
- mandatory/other movement, sorting metadata and subtype grouping;
- cumulative bounded viewing time and closed-session replay;
- print, email and feedback jobs plus audit evidence;
- protected PDF headers and cross-site denial;
- logout access list and policy permissions.

Run:

```bash
ruff format --check .
ruff check .
mypy firstbrief tests tools
pytest --cov=firstbrief --cov-report=term-missing
python manage.py check
python manage.py makemigrations --check --dry-run
```

## Manual browser evidence

Completed on 24 July 2026 using the seeded reader journey at desktop and
390 × 844 mobile viewports:

- the role-aware dashboard, forthcoming text/icon cue, current BOTD and unread
  counts rendered without inaccessible colour-only meaning;
- sortable Mandatory and Other tables exposed meaningful headings and status
  labels;
- the viewer distinguished recorded duration from the explicit Read & Clear
  acknowledgement;
- Read retained the instruction in Mandatory, while Read & Clear moved it to
  Other with a visible Cleared label;
- email-to-self and feedback displayed queued confirmations; and
- logout listed the message accessed during the browser session.

Protected PDF authorization, private caching and cross-site denial are covered
by the automated endpoint tests.
