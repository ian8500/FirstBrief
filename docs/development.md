# Developer setup

## Prerequisites

- Python 3.12
- Docker with Compose (recommended for PostgreSQL and Redis)
- An authorised local copy of the controlling PDF only when regenerating requirements

## Native development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements/dev.txt
cp .env.example .env
export DJANGO_READ_DOT_ENV=true

docker compose up -d postgres redis
python manage.py migrate
python manage.py seed_development
python manage.py runserver
```

Open `http://localhost:8000/`. Liveness is `/health/live/`; readiness is
`/health/ready/`.

The seed command creates identity reference data but no account unless
`FIRSTBRIEF_DEVELOPMENT_ADMIN_PASSWORD` is set to a password satisfying the
current policy. The development-only administrator user ID is `demo-admin`.

## Full container environment

```bash
docker compose up --build
docker compose run --rm web python manage.py seed_development
```

The application is exposed at `http://localhost:8001/` by default. Set
`FIRSTBRIEF_PORT` to choose another host port. PostgreSQL and Redis remain
private to the Compose network.

## Quality checks

```bash
make lint
make typecheck
make test
python manage.py makemigrations --check --dry-run
python manage.py check
```

To exercise PostgreSQL locally, set `DATABASE_URL` to the Compose PostgreSQL
service or run the containerised test profile:

```bash
docker compose --profile test run --rm test
```

## Configuration rules

- Production settings require an explicit secret key and allowed-host list.
- Production also requires an approved external authentication backend or an
  explicit decision to enable the local fallback.
- Secrets must not be placed in `SystemSetting`, fixtures, `.env.example`, or Git.
- UTC is authoritative. `FIRSTBRIEF_SITE_TIMEZONE` controls future display logic.
- Request logs contain method and path but intentionally exclude query strings,
  request bodies, cookies, and credentials.
- A supplied `X-Request-ID` is accepted only when it matches the restricted safe
  character set; otherwise the server generates a UUID.

## Migrations

Create migrations with `python manage.py makemigrations`. Review generated SQL
and test both clean installation and upgrades before merging. Application startup
does not silently create migrations.

Prompt 2 establishes the custom user model before the first production baseline.
Prompt 1 Compose volumes were explicitly development-only and cannot be upgraded
in place after Django's built-in admin migration has created references to the
default user table. Preserve any needed development fixture inputs, then start a
fresh named Compose project/volume for Prompt 2. Production environments must be
created from the Prompt 2-or-later migration baseline; no production data
migration from the Prompt 1 engineering prototype is supported.
