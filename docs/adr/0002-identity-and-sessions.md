# ADR 0002: Federated identity with secure local fallback

- Status: Accepted with product/security configuration decision pending
- Date: 2026-07-23

## Decision

Prefer corporate OIDC/SAML SSO with MFA. Where local authentication is explicitly enabled, use Argon2, rate limiting, configurable lockout/session timeout, and single-use time-limited reset links. Never email plaintext passwords. Do not impose a maximum below 64 characters.

Prompt 2 implements the fallback behind an explicit environment switch and
keeps the external backend import path configurable for an approved OIDC/SAML
adapter. The legacy 6–14 character and emailed-password requirements are
replaced with 12–128 characters, three of four character categories,
identity-string exclusion, Argon2, and either a single-use reset link or an
authorised administrator-only one-time display. Temporary values are never
logged or emailed.

## Consequences

This safely preserves the recovery outcome of FR-A02/A03 while intentionally replacing dated mechanisms. The deployment must document identity-provider claims, joiner/mover/leaver ownership, break-glass access, and local-auth policy.
