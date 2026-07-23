# Deployment guide

## Runtime topology

Deploy separate web, Celery worker and singleton Celery Beat processes from the same immutable image.
Provide managed PostgreSQL, Redis or an approved broker, protected object storage,
email, secrets management, TLS termination, metrics, and central logs.

## Required configuration

- `DJANGO_SETTINGS_MODULE=firstbrief.settings.production`
- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY` from a secrets manager
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` using a least-privilege application role and TLS
- `CACHE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- approved email backend/from address
- `FIRSTBRIEF_SITE_TIMEZONE`

Production refuses to start without a secret key and allowed hosts. Set proxy
forwarding so only the trusted reverse proxy can supply `X-Forwarded-Proto`.

## Release procedure

1. Build and scan the immutable image from a reviewed commit.
2. Run formatting, typing, tests, dependency audit, and `check --deploy`.
3. Back up the database and verify recovery readiness.
4. Run `python manage.py migrate --noinput` as a one-off release task.
5. Deploy web processes and confirm `/health/live/` and `/health/ready/`.
6. Deploy workers and invoke `firstbrief.core.worker_ping`.
7. Deploy exactly one Beat scheduler and confirm the three
   `firstbrief.notifications.*` periodic tasks are firing.
8. Observe error rate, latency, database health, worker connectivity, outbox age,
   lifecycle lag, retry counts and dead-letter counts.

Do not run migrations concurrently from every web replica in production.

## Rollback

Application rollback uses the previously approved image. Database rollback must
follow a reviewed migration-specific plan; never reverse a data migration
automatically. If a migration is not backward compatible, use expand/migrate/
contract deployment steps across releases.

## Baseline operations

- Liveness proves only that the process can serve requests.
- Readiness requires a successful database query.
- Correlation IDs are returned as `X-Request-ID` and included in JSON logs.
- Alert on sustained readiness failures, 5xx responses, worker loss, broker
  disconnection, and migration failures.
- Alert when pending outbox/lifecycle work is older than its operating threshold
  or any dead-letter count is non-zero. Authorised operators can inspect and
  manually resend notification deliveries at `/notifications/manage/`.
- Backups, restore cadence, availability, RTO, and RPO remain pending named-owner
  approval under NFR-01.
