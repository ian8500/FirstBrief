# ADR 0002: Federated identity with secure local fallback

- Status: Accepted with product/security configuration decision pending
- Date: 2026-07-23

## Decision

Prefer corporate OIDC/SAML SSO with MFA. Where local authentication is explicitly enabled, use Argon2, rate limiting, configurable lockout/session timeout, and single-use time-limited reset links. Never email plaintext passwords. Do not impose a maximum below 64 characters.

## Consequences

This safely preserves the recovery outcome of FR-A02/A03 while intentionally replacing dated mechanisms. The deployment must document identity-provider claims, joiner/mover/leaver ownership, break-glass access, and local-auth policy.

