# Release candidate runbook

## Gate

```bash
ruff check .
mypy firstbrief tests
python manage.py makemigrations --check --dry-run
python manage.py check --deploy --settings=firstbrief.settings.production
pytest --cov=firstbrief --cov-fail-under=80
pip-audit --requirement requirements/base.txt
python manage.py release_evidence
```

## Clean deployment

Build immutable images, provide production secrets, run migrations once, start
web/worker/beat, then verify `/health/live/` and `/health/ready/`. Production
terminates TLS at an approved proxy and sends `X-Forwarded-Proto: https`.

## Upgrade and rollback

Back up PostgreSQL and protected object storage before migration. Test the
migration against a restored production-like copy. Application rollback may use
the previous image only while its schema is compatible; otherwise restore the
verified backup under incident control.

## Recovery acceptance

Restore the database and protected objects in an isolated environment, run
`release_evidence`, compare continuity-export SHA-256 evidence, exercise login,
dashboard, one message read, one report and one import preview, and record RTO/RPO
against formally approved targets.

## Outstanding approvals

Corporate identity claims, SAP contract/landing authentication, retention
periods, export classification/expiry, malware scanner, NATS brand approval and
numeric availability/RTO/RPO require their accountable owners.
