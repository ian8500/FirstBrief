# Prompt 2 verification report

## Summary

Prompt 2 implements the identity and access phase gate: users, sites, groups,
supervisor relationships, roles, granular capabilities, message-type grants,
report inclusion, default-group validation, configurable security policy,
server-side site scope, secure local authentication, account recovery,
append-only audit evidence, and accessible self-service/administration screens.

## Security decisions

- Corporate OIDC/SAML remains the preferred production mechanism and is
  pluggable through an explicit authentication-backend setting.
- Local authentication is explicit, Argon2-based, rate limited and locked after
  a configurable threshold.
- Legacy emailed plaintext passwords are replaced by time-limited, single-use
  reset links or an authorised one-time display.
- Passwords use 12–128 characters, three of four categories, and exclude the
  user ID and names. This supersedes the obsolete 6–14 character ceiling.
- Authorisation and site scope are enforced in services/querysets; hiding a
  menu is never treated as the security boundary.
- Audit events reject application updates and deletes.

## Implemented outputs

- Custom user, role, capability, site, group, message-type and supervisor models.
- Default role and default-group integrity constraints and validation.
- Direct and role-granted permissions with deny-by-default checks.
- Site-scoped user queries and See All Primary Message Groups override.
- Configurable expiry, warning, lockout, session and notification settings.
- Login, profile, password change/reset, logout confirmation, scoped user search,
  user creation and administrative password-reset screens.
- Forced password change after initial or administrator reset.
- Development-only, opt-in administrator seeding without a committed password.

## Deferred integration points

- The approved corporate identity provider and claims contract require deployment
  owner input before an OIDC/SAML adapter can be activated.
- Message access entries on logout are structurally supported by the session; the
  consuming message workflow populates them in Prompt 6.
- Approval and unapproved-effective notification addresses are persisted here;
  delivery orchestration is implemented in Prompt 5.
- Prompt 2 establishes Django's custom user model as the first production data
  baseline. Prompt 1 development-only volumes are preserved but not upgraded in
  place; a fresh named development stack is required.

## Verification results

- Ruff formatting and linting: passed.
- Mypy strict typing: passed for 48 source files.
- Local tests: 41 passed with 92.51% application coverage.
- Migration drift and Django system checks: passed.
- PostgreSQL container tests: 37 passed and 4 controlled-source tests skipped,
  with 92.51% application coverage.
- Fresh production-image migration, web readiness and Celery worker ping: passed.
- Browser review: semantic banner/main/region, one H1, two associated labels,
  correct credential autocomplete, accessible error alert, no duplicate error,
  and no horizontal overflow.
- Dependency audit: no known vulnerabilities found.

## Next recommended prompt

Prompt 3 — Configuration taxonomy.
