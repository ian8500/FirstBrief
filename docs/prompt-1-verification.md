# Prompt 1 verification report

## Summary

Prompt 1 is complete at the engineering-foundation gate. FirstBrief now has a
runnable Django 5.2 LTS application, PostgreSQL persistence, Redis/Celery worker
wiring, secure environment settings, health/readiness probes, correlation-aware
JSON logging, baseline security headers, accessible server-rendered UI, CI,
containers, migrations, seed fixtures, and developer/deployment documentation.

No operational message, identity, taxonomy, or reporting feature has been
claimed as implemented.

## Decisions

- Django 5.2.16 LTS on Python 3.12 with DRF 3.17.1.
- PostgreSQL 16.14 and Redis 7.4 for the local/CI baseline.
- Celery 5.6.3 behind an application-owned job-dispatch interface.
- Production settings fail closed without an explicit secret key and allowed hosts.
- UTC is authoritative; a configured IANA site timezone is retained for display.
- Structured logs exclude query strings, bodies, cookies, and credentials.
- The controlled source PDF remains excluded from images and Git.

## Implemented scope

- Split development, test, and production settings.
- PostgreSQL/SQLite test support and initial `SystemSetting` migration.
- Safe, idempotent development fixture command that refuses non-development use.
- Liveness and database-backed readiness endpoints.
- Validated/generate-on-failure `X-Request-ID` handling and JSON logs.
- Content-negotiated error responses carrying support references.
- Secure cookie, CSRF, HSTS, proxy, CSP, permissions, frame, referrer, and upload baselines.
- Non-root multi-stage production/development images and Compose services.
- Web, worker, PostgreSQL, Redis, and test health/test profiles.
- GitHub Actions quality, PostgreSQL integration, dependency audit, and deploy checks.
- Accessible responsive foundation screen with a skip link and semantic status content.

## Verification results

- Ruff format: passed (51 files).
- Ruff lint: passed.
- Mypy strict typing: passed (24 source files).
- Django system check: passed.
- Migration drift check: passed.
- Local tests: 20 passed, 87.65% combined application/tooling coverage.
- PostgreSQL container tests: 15 passed; 4 controlled-PDF tests skipped as designed;
  95.92% application coverage.
- Django production `check --deploy`: passed.
- Installed-environment dependency audit: passed with no reported vulnerabilities.
- Compose configuration: valid.
- Production and development container images: built successfully as non-root.
- Clean PostgreSQL migration: passed.
- Web liveness/readiness: healthy and returned HTTP 200.
- Celery/Redis worker: healthy and returned `pong`.
- Browser review: one H1, semantic banner/main/region, working stylesheet, skip link,
  no horizontal overflow at 1280×720, and clean visual hierarchy.

## Known limitations and risks

- Availability, RTO, RPO, backup, and restore targets still need named-owner approval.
- Full identity/authorisation begins in Prompt 2.
- Append-only audit, outbox/dead-letter handling, file quarantine/scanning, concurrency,
  and performance evidence are deliberately deferred to their ordered prompts.
- Port 8000 is occupied by another local Python process, so Compose defaults to host
  port 8001.
- The local container volumes contain development-only data.

## Next recommended prompt

Prompt 2 — Identity, authentication and authorisation, after this gate is reviewed.
