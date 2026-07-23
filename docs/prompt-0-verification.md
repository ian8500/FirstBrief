# Prompt 0 verification report

## Summary

Prompt 0 is complete at the design gate. The controlling 52-page PDF was copied into the workspace, checksummed, fully processed, and converted into a 121-record authoritative register. Both source sections are represented. Seventeen implementation-guide gap closers are separately marked `Proposed`.

No application feature code has been implemented.

## Decisions

- Modular Django monolith with explicit domain services.
- PostgreSQL system of record, protected object storage, transactional outbox, idempotent workers.
- Federated SSO/MFA preferred; secure local fallback replaces emailed plaintext temporary passwords.
- UTC storage with configured IANA site timezone.
- Append-only audit and service/query-level authorisation.
- Versioned report catalogue rather than one-off report implementations.

## Files produced

- Source/registers: source PDF, source register, requirements register, proposed supplemental register, traceability matrix.
- Design: solution, domain model, lifecycle state machine, threat model, NFRs, prioritised backlog.
- Decisions: six ADRs covering architecture, identity, audit, files, jobs, and reporting.
- Review: implementation-guide review and detailed requirements review.
- Tooling: deterministic page-aware requirements extractor.

## Commands and results

- PDF metadata/text extraction: 52 pages processed.
- SHA-256: `1d40779b51a245b58a5a29dceef5d0f2ba441ad0816fead8a9a3290b60336e04`.
- Extractor validation: 121 unique detailed IDs; no incomplete required fields.
- Coverage: 69 operational/functional and 52 administration/configuration requirements.
- Traceability: 121 source requirements marked `Designed`; 17 gap closers marked `Proposed`.
- Extractor unit tests: 4 passed.
- Python compile check: passed.
- Application format/type/integration suites: not applicable before the Prompt 1 engineering toolchain exists.
- DOCX structural inspection: passed; 266 paragraphs, 10 tables, consistent named styles.
- DOCX visual render: not run because LibreOffice/`soffice` is unavailable.

## Open risks

Product/security/records/integration owners must decide audience precedence, lifecycle edge semantics, NFR numeric targets, retention/legal hold, identity mode, SAP contract, file policy, export controls, and delegated/bulk acknowledgement rules. All 121 source requirement owners are still `TBD`.

Repository isolation was resolved on 2026-07-23: the FirstBrief workspace is now its own Git repository on `main`, with `origin` set to `https://github.com/ian8500/FirstBrief.git`. The remote is public, so the NATS Internal source PDF is ignored and controlled material must not be pushed without information-classification approval.

## Next recommended prompt

Prompt 1 — Engineering foundation, after the Prompt 0 artefacts and open-decision ownership are accepted.
