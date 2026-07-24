# Prompt 7 verification

## Source review

The complete 52-page controlling requirements PDF was processed before coding.
All 52 rendered pages were visually checked and extracted text from both the
Operational / Functional and Admin / Configuration sections was reviewed.

## Assumptions and safer interpretations

- “No criteria returns all” means all published messages the actor is authorised
  to retrieve, never drafts or records outside role/site/type/group scope.
- Archived and not-yet-effective records are opt-in.
- Legacy “delete” is represented by audited withdraw/cancel/archive lifecycle
  actions because messages and versions are retained records (ADR 0007).
- PDF content indexing uses bounded post-scan extraction; image-only PDFs are not
  OCR’d implicitly (ADR 0009).
- User lookup is site-scoped unless See All PMG is granted.

## Delivered

- Combined BOTD and Instruction search by ID, title, summary, display content,
  group, subtype, read state and release/effective/expiry ranges.
- Archived/future toggles, allow-listed stable sorting and 25-row pagination.
- Three-character Message ID and user suggestions with the required user label.
- Protected search-result viewer and scope-identical, bounded CSV export.
- Data-authority maintenance filters, stable pagination and status/capability
  action policy.
- Capability-controlled chronological message audit history.
- Identifier/title/date indexes plus versioned protected-content text.

## Automated evidence

`tests/test_retrieval.py` covers:

- combined filter reconciliation and current-version content;
- archived and future opt-in behaviour;
- site, role, type, group and Prohibited isolation across counts, suggestions,
  detail views and CSV;
- user and Message ID suggestion thresholds and display formats;
- stable pagination and bounded database-query count;
- maintenance status filters, See All PMG and permitted action matrices; and
- audit-history capability enforcement and export auditing.

The complete suite, formatting, lint, static typing, migration drift, Django
checks and coverage gate are run before publication.

## Manual browser evidence

Completed on 24 July 2026 at desktop and 390 × 844 mobile viewports:

- default search returned only the currently effective permitted message;
- Message ID and user suggestions announced results after three characters;
- combined display-content search plus archive/future toggles returned effective,
  archived and forthcoming records with accessible table headings;
- an archived result opened through the protected scoped viewer;
- the maintenance grid displayed group/subtype/status filters and a
  status-specific Permitted actions column; and
- search controls, date inputs, results and navigation remained usable at the
  mobile breakpoint.
