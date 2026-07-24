# ADR 0009: Scope-first retrieval and protected content indexing

## Status

Accepted.

## Context

Prompt 7 requires combined message search, counts, suggestions and export while
proving that prohibited or cross-site records cannot leak through any surface.
Instructions use protected PDFs, so display-content search must not make a source
file public or bypass upload controls.

## Decision

Every retrieval path begins with the same server-side role, message-type, site,
group and Prohibited-precedence queryset. Criteria, counts, sorting, pagination,
suggestions and export are applied only after that scope. There is no unscoped
count or suggestion query.

Display-PDF text is extracted only after PDF validation and malware scanning.
Extraction is bounded to 200,000 characters and stored with the immutable message
version. The PDF remains in opaque protected storage and the search viewer
repeats scope authorization before streaming it.

Exports are capped, marked private/no-store, formula-prefixed cells are escaped,
and each export appends an audit event.

## Consequences

- All retrieval consumers share one authorization boundary.
- Image-only PDFs cannot be searched by visual text until approved OCR exists.
- Bounded extraction and export prevent unbounded request memory.
- Specialised PostgreSQL full-text indexes can be added later without changing
  the authorization contract.
