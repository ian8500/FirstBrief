# FirstBrief

FirstBrief is a secure, auditable operational briefing application for creating,
approving, releasing and retaining Brief of the Day (BOTD) and Instruction
messages.

This README is the living technical and end-user manual for the project. Every
functional change must update the relevant sections here in the same commit.
Detailed design decisions and phase evidence remain in `docs/`.

## Current delivery status

Prompts 0–6 are implemented and verified.

| Phase | Delivered capability |
| --- | --- |
| Prompt 0 | Requirements register, traceability, architecture, threat model and delivery backlog |
| Prompt 1 | Django foundation, PostgreSQL, Redis, Celery, health checks, containers and CI |
| Prompt 2 | Users, roles, capabilities, scoped access, secure local authentication and audit |
| Prompt 3 | Sites, groups, message types, subtypes, approval and distribution configuration |
| Prompt 4 | Message authoring, immutable versions, approval, lifecycle commands, PDFs and audience rights |
| Prompt 5 | Transactional outbox, scheduled lifecycle transitions, notifications, retries and operational recovery |
| Prompt 6 | Operational dashboard, reader lists, secure viewer, acknowledgement and access evidence |

The controlling requirements contain 121 inventoried source requirements.
Seventeen proposed gap-closing requirements are tracked separately and are not
silently treated as approved source requirements.

## Quick start

### Container environment

Prerequisites: Docker with Compose.

```bash
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

Open `http://localhost:8001/` and sign in at
`http://localhost:8001/access/login/`.

No default password or reusable login is committed to the repository. The
`createsuperuser` command prompts you to create local demonstration credentials.
Use a non-production password and do not reuse a personal or corporate password.

Stop the environment with:

```bash
docker compose down
```

PostgreSQL and Redis data are retained in named development volumes. Use
`docker compose down --volumes` only when you intentionally want to destroy that
local data.

### Native development

Prerequisites: Python 3.12, PostgreSQL and Redis.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements/dev.txt
cp .env.example .env
export DJANGO_READ_DOT_ENV=true
python manage.py migrate
python manage.py seed_development
python manage.py runserver
```

The native server defaults to `http://localhost:8000/`. To create the optional
development administrator, set
`FIRSTBRIEF_DEVELOPMENT_ADMIN_PASSWORD` to a policy-compliant password before
running `seed_development`. Its user ID is `demo-admin`.

## End-user manual

### Sign in and account management

1. Open `/access/login/`.
2. Enter the user ID and password supplied by an authorised administrator.
3. If prompted, change a temporary or expired password before continuing.
4. Use **Profile** to review your account and **Change password** to replace a
   local password.
5. Use the reset link on the login page if password-reset email is configured.

Local authentication uses Argon2 password hashing, configurable lockout and
time-limited single-use reset links. Production deployments should use the
approved corporate identity provider when its claims contract is available.

### Roles and access

Access is deny-by-default and is enforced on the server. A hidden navigation item
does not grant or remove permission.

The principal capabilities are:

- **Create messages** — create BOTD and Instruction messages.
- **Approve messages** — approve messages assigned to the user.
- **Manage messages** — revise messages, perform authorised lifecycle actions,
  configure notification operations and resend failed notifications.
- **Manage configuration** — maintain sites, primary message groups, message
  groups, message types and subtypes.
- **Manage users/roles/identity settings** — administer accounts and security
  policy.
- **See all primary message groups** — override normal site/group visibility
  where expressly authorised.

Users normally see only messages in their authorised site and group scope.

### Use the operational dashboard

After sign-in, the dashboard at `/` shows:

- mandatory messages that became effective since the previous login, even when
  they have already been read or cleared;
- messages inside the configured forthcoming window, identified by a diamond,
  the word **Forthcoming** and the configured colour;
- current Briefs of the Day for the default message group, or every applicable
  group when no default is set;
- unread counts and links to Mandatory and Other Messages.

The **Mandatory** and **Other messages** navigation is available to signed-in
users. Message results are still restricted on the server by active role,
message-type permission, site, group membership and audience rights. A
Prohibited right takes precedence over Allowed or Mandatory.

### Read and acknowledge messages

Open **Mandatory** to see required messages or **Other messages** for reference
content and messages already cleared. Both lists can be sorted by Message,
Effective, Expires, Printed or Emailed and grouped by subtype with unread counts.
Unread, overdue and forthcoming states always include text or a symbol; colour is
not the only cue.

Opening a message records an access event and starts a viewing session. BOTD text
appears directly; Instructions display their protected PDF through an authorised,
private, same-origin endpoint.

When finishing a mandatory message:

1. Choose **Read** to record reading and keep it in Mandatory Messages.
2. Choose **Read & Clear** to make the compliance acknowledgement and move it to
   Other Messages.
3. Select **Confirm and close**.

Foreground, non-idle viewing seconds are accumulated across sessions. This
duration is supporting information; **Read & Clear**, not elapsed time, is the
compliance action. Closed viewing sessions cannot be replayed to add evidence.

The viewer also provides:

- **Print**, which records the event and opens a print-friendly view;
- **Email to me**, which queues delivery to the address on your profile;
- **Send feedback**, pre-populated with message metadata and delivered to the
  originator and authorised administrators.

Instruction email contains an authenticated link rather than attaching the
protected PDF. On logout, the confirmation page lists messages accessed during
the browser session.

Configuration managers can use `/operational/settings/` to set the forthcoming
window, forthcoming colour and idle timeout. The colour setting is always
supplemented by text and an icon.

### Configure the message taxonomy

Authorised configuration managers can open `/configuration/`.

1. Create the site and its primary message groups.
2. Add message groups beneath the correct primary group.
3. Configure message types such as BOTD or Instruction.
4. Add subtypes where a message type requires them.
5. Set subtype validity limits, approval behaviour, email distributions and
   active/inactive state.

Deactivate configuration that should no longer be selected. Deletion is blocked
where it would invalidate referenced operational records.

### Create and manage a message

Open **Messages** or `/messages/manage/`.

1. Select **Create message**.
2. Choose BOTD or Instruction and the permitted message type/subtype.
3. Enter the unique message ID, title, summary and content.
4. Set release, effective and expiry times as required by the selected type.
5. Assign audience groups and approvers.
6. For Instructions, upload the required protected display/print PDFs.
7. Submit the form and review the message detail page.

Instructions and BOTD share one message aggregate. Revisions create immutable
versions; they do not overwrite historical content. Concurrent changes are
rejected through optimistic locking so that one editor cannot unknowingly replace
another editor's work.

PDF uploads are parsed strictly, stored under opaque keys, checksummed and passed
through a fail-closed malware-scanner interface. Production must configure an
approved working scanner.

### Approval and lifecycle

The message detail page shows the actions permitted for the current user and
state. Supported actions are approve, unapprove, release, make effective, expire,
archive, withdraw, cancel and restore.

Approval records the approver, time and justification. Withdrawal and archive
preserve the record and audit trail; application users do not physically delete
messages. Scheduled transitions run automatically when their configured time is
due, and late workers catch up safely when they restart.

A typical path is:

```text
Draft -> Approved -> Released -> Effective -> Expired -> Archived
```

Not every message uses every state. Invalid transitions are rejected by the
domain service, and repeated execution of the same command is idempotent.

### Notification operations

Users with **Manage messages** can open `/notifications/`.

The page allows an authorised operator to:

- choose whether creation and approval email timing is anchored to the event,
  release time or effective time;
- apply positive or negative minute offsets independently of message visibility;
- define quiet hours in an IANA timezone;
- set retry limits, retry delay and archive-retention review timing;
- see recent deliveries and outbox, lifecycle or notification dead letters;
- manually requeue a failed notification.

Email recipients are resolved from assigned approvers, subtype distributions and
the configured identity-policy alert addresses. Duplicate processing does not
send the same logical notification twice. Failed deliveries retry with bounded
exponential delay and become visible as dead letters when exhausted.
Reviewed text templates provide creation, approval and unapproved-at-effective
email content. Quiet hours are checked again immediately before delivery so a
delayed worker cannot send during a suppressed period.

Retention jobs currently mark and audit records for review. They do not purge
message data. Prompt 10 will add legal holds, purge preview/approval and purge
evidence before destructive retention is enabled.

### Health checks

- `/health/live/` confirms that the web process is running.
- `/health/ready/` confirms that required dependencies are ready.

These endpoints are intended for local diagnosis and deployment probes, not as a
substitute for the notification dead-letter operations page.

## Technical manual

### Architecture

FirstBrief is a Django 5.2 LTS application backed by PostgreSQL. Redis provides
the Celery broker/result backend. Gunicorn serves the production web process,
Celery workers execute recoverable work and Celery Beat dispatches the periodic
database-backed processors.

The main bounded components are:

- `firstbrief.identity` — users, roles, capabilities, authentication policy and
  audit.
- `firstbrief.configuration` — sites, groups, message types and subtypes.
- `firstbrief.messaging` — messages, immutable versions, approval, audience,
  protected files and lifecycle state.
- `firstbrief.notifications` — transactional outbox, lifecycle schedule,
  notification policy, delivery retries and recovery operations.
- `firstbrief.operations` — scoped dashboard queries, reading receipts,
  append-only access events, viewing sessions and acknowledgement workflows.
- `firstbrief.core` — application shell, error handling, request correlation,
  health checks and shared audit services.

UTC is authoritative in persistence and scheduling. User-facing quiet-hour
calculation uses the configured IANA timezone and handles daylight-saving
transitions.

### Transaction and worker model

Message creation and approval write their notification request to `OutboxEvent`
inside the same database transaction. A committed message therefore cannot
diverge from its notification intent.

Celery Beat dispatches three idempotent processors every minute:

1. outbox processing materialises deduplicated notification jobs;
2. lifecycle processing applies due release, effective, expiry, archive,
   retention-review and unapproved-at-effective work;
3. delivery processing sends due email and records retry, dead-letter and audit
   evidence.

Email content is stored in `templates/notifications/email/`, keeping operational
copy reviewable without embedding it in worker code. Quiet hours are enforced at
both initial scheduling and actual delivery.

Operational email-to-self and feedback requests are persisted as notification
jobs and use the same recoverable delivery worker. Structured access events are
append-only; mutable `MessageReceipt` rows hold each user’s current read, cleared,
printed, emailed and cumulative viewing state.

The database is authoritative. A worker outage delays execution but does not lose
the schedule; overdue jobs are processed after recovery. Run only one Beat
scheduler per environment to avoid unnecessary duplicate dispatch.

### Configuration

Copy `.env.example` for native development. Important settings include:

| Setting | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | Select development, test or production settings |
| `DJANGO_SECRET_KEY` | Cryptographic application secret; mandatory in production |
| `DJANGO_ALLOWED_HOSTS` | Permitted HTTP host names |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Trusted browser origins |
| `DATABASE_URL` | PostgreSQL connection |
| `CACHE_URL` | Django cache connection |
| `CELERY_BROKER_URL` | Celery broker |
| `CELERY_RESULT_BACKEND` | Celery result store |
| `FIRSTBRIEF_SITE_TIMEZONE` | Default display timezone |
| `FIRSTBRIEF_LOCAL_AUTH_ENABLED` | Explicitly enable local login |
| `FIRSTBRIEF_EXTERNAL_AUTH_BACKEND` | Approved external authentication backend |
| `FIRSTBRIEF_MALWARE_SCANNER` | Protected-file scanner implementation |
| `EMAIL_BACKEND` | Django email backend |
| `LOG_LEVEL` | Application log threshold |

Never place credentials, API keys or production secrets in database system
settings, fixtures, `.env.example` or Git.

### Database and seed data

Apply migrations after each deployment:

```bash
python manage.py migrate --noinput
```

Development reference data is loaded idempotently with:

```bash
python manage.py seed_development
```

The seed command is deliberately blocked outside the development environment.
Production data must be created through an approved administrative process.

### Quality and security checks

Run the complete local gate before committing:

```bash
make check
python -m pip_audit --requirement requirements/base.txt
```

The expanded commands are:

```bash
ruff format --check .
ruff check .
mypy firstbrief tests tools
pytest --cov=firstbrief --cov-report=term-missing
python manage.py check
python manage.py makemigrations --check --dry-run
```

CI also exercises PostgreSQL and production settings. Prompt-specific evidence is
recorded in `docs/prompt-N-verification.md`.

### Production deployment checklist

1. Build an immutable image from a reviewed commit.
2. inject the secret key, allowed hosts, trusted origins, database, cache,
   broker, email, identity-provider and malware-scanner configuration from an
   approved secret store;
3. run `python manage.py check --deploy`;
4. back up the database and apply migrations;
5. start the web service, Celery workers and exactly one Celery Beat service;
6. verify liveness, readiness and worker health;
7. monitor application errors plus outbox, lifecycle and notification dead
   letters;
8. retain rollback evidence and follow the environment change process.

See `docs/deployment.md` for the operational detail.

### Troubleshooting

- **Login rejected:** confirm local authentication is explicitly enabled, the
  account is active and not locked, and the password has not expired.
- **No menu item:** the account lacks the required capability or site/group
  scope; ask an authorised administrator to review the assignment.
- **Expected message is missing:** confirm the user has an active role granting
  its message type, matching site/group membership, no Prohibited audience right,
  and that a forthcoming message is inside the configured window.
- **Viewing time did not increase:** time is credited when the viewer is closed;
  it pauses while the tab is hidden or the reader is idle.
- **Read message remains mandatory:** choose Read & Clear when closing to record
  the compliance acknowledgement.
- **Scheduled state did not change:** confirm Redis, the worker and the single
  Beat service are healthy, then inspect lifecycle dead letters.
- **Email not delivered:** check the email backend, recent notification status
  and dead letters at `/notifications/`; resend only after correcting the cause.
- **PDF rejected:** confirm it is a valid PDF, meets the configured naming rule
  and passes the configured malware scanner.
- **Migration drift:** run `python manage.py makemigrations --check --dry-run`;
  never generate migrations automatically during application startup.
- **Port already in use:** set `FIRSTBRIEF_PORT`, for example
  `FIRSTBRIEF_PORT=8003 docker compose up --build`.

## Controlled requirements source

The controlling requirements PDF is marked **Internal** and is intentionally
excluded from Git. Place an authorised copy at:

`docs/source/FirstBrief_Master_Requirements_TwoSections.pdf`

Then regenerate and verify the registers:

```bash
python tools/extract_requirements.py \
  docs/source/FirstBrief_Master_Requirements_TwoSections.pdf \
  --register docs/requirements/requirements-register.csv \
  --traceability docs/requirements-traceability.csv

python -m unittest discover -s tests -v
```

Do not publish controlled source material without the required
information-classification approval.

## Further documentation

- `docs/development.md` — developer setup and migration rules.
- `docs/deployment.md` — production deployment and recovery.
- `docs/solution-design.md` — solution boundaries and architecture.
- `docs/domain-model.md` — domain concepts and relationships.
- `docs/message-lifecycle.md` — lifecycle rules.
- `docs/threat-model.md` — threats and mitigations.
- `docs/requirements-traceability.csv` — implementation evidence by requirement.
- `docs/adr/` — architecture decision records.

The next product phase is Prompt 7: scoped search and maintenance.
