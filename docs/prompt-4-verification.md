# Prompt 4 verification

## Delivered

- Unified BOTD and Instruction `Message` aggregate with immutable UUID identity,
  unique external message ID, immutable versions, optimistic locking, approvals,
  audience rights and complete status history.
- Transactional lifecycle commands for approval, unapproval, release, effective,
  expiry, archive, withdrawal, cancellation, restoration and supersession.
- Date, content, subtype/PMG, assigned-approver and audience validation.
- Configurable protected PDF upload handling with strict parsing, opaque quarantine
  keys, SHA-256 checksums, fail-closed malware-scanner interface and optional
  filename matching.
- Scoped authoring/list/detail UI with native date-time inputs and group/subtype
  filters.
- Initial messaging migration and development seed data/capabilities.

## Automated evidence

Run:

```bash
ruff check .
mypy firstbrief
pytest
python manage.py check
python manage.py makemigrations --check
```

Prompt-specific tests are in `tests/test_messaging.py`. They cover immutable
identity/versioning, validation, approval evidence, assigned approvers, optimistic
locking, idempotency, all lifecycle states, withdrawal/cancellation/restoration,
supersession, audience precedence, protected PDF storage and UI permission/date
controls.

## Requirement interpretation

FR-C03’s legacy “delete” action is implemented as record-preserving
withdrawal/archive, as recorded in ADR 0007. FR-K01–FR-K03 have working
implementations but remain Proposed requirements until formal approval.
