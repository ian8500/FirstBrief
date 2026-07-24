# Operational message reader

## Security and evidence model

Protected PDFs remain behind
`/operational/messages/<message>/files/<asset>/`. The endpoint authenticates the
request, applies role/message-type/site/group/audience scope, enforces Prohibited
precedence, checks that the asset belongs to the current clean version, and
returns `Cache-Control: private, no-store`. Reader navigation never constructs a
storage or public object URL.

Evidence is deliberately separated:

1. **Opened** records the authorised reader session and message version.
2. **Read** records bounded foreground, focused and non-idle time when the user
   finishes.
3. **Acknowledged** records the explicit compliance decision for the opened
   version.
4. **Cleared** moves that acknowledged Mandatory message to Other Messages.

The server caps submitted time to elapsed session time and 14,400 seconds.
Closed sessions cannot be replayed. Background, unfocused and idle browser time
is not incremented by the client.

If status, audience or version changes while the reader is open, periodic status
checking disables acknowledgement. On submission the server independently
revalidates the current message. Reading time is retained, but no Acknowledged
or Cleared event is emitted.

## Reader functions

- Version-scoped last page and progress persist per user.
- PDF bookmarks are shown as a table of contents when present.
- Page preview cards and embedded-text search are generated after authorisation.
- J/K moves through pages; `/` focuses PDF search; `[` and `]` move through the
  user's scoped Mandatory sequence; `?` opens keyboard help.
- Previous/next Mandatory and related-message links are derived only from the
  same authorised operational query used by the lists.
- Supersedes/superseded-by and live cancelled/withdrawn/version-change states are
  explicit.
- Print uses the audited print endpoint and print-specific layout.

Text search is available only when the PDF contains extractable text. Page
previews are protected text-based thumbnail representations; the source PDF is
never copied to a public thumbnail location.

## User guide

Open a message from Dashboard, Mandatory or Other Messages. For an Instruction:

1. Use **Contents**, **Page thumbnails**, J/K or the embedded viewer to move
   through pages.
2. Use **Search this PDF** for text embedded in the protected document.
3. Check **Reading progress**; reopening the same version resumes its last saved
   page.
4. Use Previous/Next Mandatory only when another authorised uncleared item is
   available.
5. Review lifecycle and version banners before relying on the content.
6. Under **Finish reading**, choose **Mark as read** or, for Mandatory content,
   **Acknowledge and clear**.

If the message changes while open, follow the alert and reopen the current
message from the list. The application records the safe reading evidence but
does not accept the stale acknowledgement.

## Accessibility and responsive behaviour

The PDF frame has a message/version-specific title. Reader tools use labelled
regions, headings, progress semantics, live search/status messages and normal
buttons/links. The modal help panel restores focus to its opener. At tablet and
mobile widths, the PDF tools stack above the viewer and thumbnails become a
horizontal, keyboard-operable strip without page-level overflow.

## Verification record

On 24 July 2026:

- Ruff, mypy, migration-drift and production deployment checks passed.
- The full suite passed: 130 tests passed and 4 were skipped.
- Coverage was 85.41%, above the required 80%.
- Browser validation passed at 1280, 768 and 390 px. Bookmark navigation,
  protected-text search, page persistence, help-dialog focus and responsive
  overflow checks passed with no console warnings.
- Release evidence reported ready.
- The exact isolated `pip-audit --requirement requirements/base.txt` remained
  inconclusive because this environment stalled while bootstrapping pip in its
  temporary audit environment. The supplementary direct pinned-dependency audit
  reported no known vulnerabilities; it does not cover transitive dependencies.
