# Implementation guide review

## Overall assessment

The guide is a strong implementation blueprint and is suitable for phased Codex delivery. It correctly prevents one oversized build prompt, makes the 52-page PDF controlling, requires traceability/tests at every gate, recommends a proportionate modular monolith, and explicitly corrects unsafe legacy authentication requirements.

The document contains 266 paragraphs, 10 tables, one section, a consistent heading ladder, one source-ingestion prompt, and Prompts 0–12. The operational, author/approver, and technical administration guides are useful target-state drafts.

## Strengths

- Clear authority hierarchy between the controlling PDF and the implementation guide.
- Good phase ordering from discovery through release verification.
- Strong cross-cutting defaults: UTC, server-side authorisation, protected files, audit, accessibility, and no production mock security.
- Appropriate use of a transactional outbox and shared domain services for interactive and scheduled actions.
- Realistic critical scenarios for DST, audience conflict, concurrency, acknowledgement, cancellation, import, and recovery.
- Explicit requirement that uncovered items remain failures rather than being silently assumed complete.

## Changes or clarifications recommended

1. Treat the “stop after each phase” instruction as a hard governance gate. A request to implement every prompt should span successive approvals, not collapse all prompts into one unauditable change.
2. Replace “Django 5 LTS when available” with “Django 5.2 LTS, latest approved security patch.” As reviewed on 2026-07-23, Django 5.2 is the supported LTS line; exact patch pinning belongs in Prompt 1.
3. Keep PostgreSQL 16+ as a minimum but select the actual production major against organisational support and upgrade policy in Prompt 1.
4. Add named decision owners and due dates. All 121 source owners are `TBD`, so the current prompt set cannot itself provide acceptance authority.
5. Add explicit phase entry criteria, especially approval of audience precedence, lifecycle semantics, retention, SAP contract, identity mode, and NFR targets.
6. Mark NFR-01–NFR-10 and FR-K01–FR-K07 as proposed until formally adopted; do not mix them invisibly with contractual source requirements.
7. Specify dependency/tool lock and software bill of materials expectations in Prompt 1.
8. Specify test data classification and synthetic-data rules before seeding representative users/messages.
9. Add a data-migration/cutover workstream if FirstBrief replaces an existing production system.
10. Add operational ownership for dead letters, failed imports, malware detections, restore tests, and expiring report/continuity exports.

## Document-quality observation

Structural inspection found consistent Word styles (`Title`, three heading levels, numbered/bulleted lists, a dedicated `Prompt` style, callouts, headers, and footers). Visual rendering could not be completed because LibreOffice is not installed in the environment, so clipping, table wrapping, and page-break quality remain unverified.

