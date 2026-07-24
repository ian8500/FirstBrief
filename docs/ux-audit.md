# FirstBrief product UX audit

Date: 24 July 2026  
Branch reviewed: `codex/full-product-ux-audit` from `origin/main`  
Scope: Prompts 0–12 as implemented, plus the current Prompt 13 release hardening.

## Method and evidence

The audit combined:

- inspection of every template under `templates/`, all URL configurations, forms,
  models, views, services, tests, the README and the requirement/verification
  documents;
- authenticated browser walkthroughs at desktop (1280 px), tablet (768 px) and
  mobile (390 px) widths using a seeded administrator and a representative
  effective mandatory briefing;
- review of keyboard/accessibility semantics, responsive overflow, permission
  gates, validation, empty states and lifecycle feedback;
- execution of the release gate documented in `docs/release-candidate.md`.

This is a UX audit, not a visual redesign. Existing behaviour is not described as
missing where it is implemented but difficult to find or use.

## What already works well

- The application uses semantic landmarks, a skip link, visible focus treatments,
  labelled fields and text/symbol status cues in addition to colour
  (`templates/base.html`, `firstbrief/core/static/css/app.css`).
- The dashboard prioritises mandatory, forthcoming and current BOTD content and
  gives useful empty states (`templates/operations/dashboard.html`).
- The reader keeps the operational message prominent and supports print,
  email-to-self, feedback and explicit close/acknowledgement
  (`templates/operations/message_viewer.html`).
- Server-side capability and site scoping is consistently more robust than the
  visible navigation, and high-risk lifecycle/import/retention operations have
  domain-level validation and audit evidence.
- Error pages expose a support-safe correlation ID, and many forms include an
  error summary (`templates/400.html`, `templates/403.html`,
  `templates/500.html`).

## Ten highest-value improvements

1. Replace the overflowing flat header with a responsive, role-aware navigation
   model and a visible current-location state (UX-01).
2. Correct Assurance routing and expose Retention and Users to authorised users
   (UX-02).
3. Make report criteria specific to each report, with progressive disclosure and
   clear required fields (UX-06).
4. Turn authoring into a type-aware, staged workflow with an audience summary and
   review step (UX-04).
5. Separate message lifecycle actions by intent and add clear consequences and
   confirmation for destructive transitions (UX-05).
6. Make retention/legal-hold controls discoverable and make the two-person purge
   flow explain who can act next (UX-10).
7. Replace desktop tables with mobile task views or priority columns rather than
   relying on horizontal scrolling (UX-03).
8. Improve SAP review with field-level before/after changes, impact and a final
   selected-update confirmation (UX-09).
9. Add accessible progress, completion and recovery states to asynchronous
   reports and notification operations (UX-07).
10. Complete user administration and recovery UX with search, pagination, edit
    affordances and safer password hand-off (UX-11).

## Issue register

### UX-01 — Flat navigation overflows and has no location state

- **User role:** All authenticated users, especially multi-capability managers.
- **Current behaviour:** All permitted destinations are rendered in one
  horizontally scrolling header. At 390 px the navigation measured 1,083 px
  inside a 358 px viewport; the same overflow remains at 768 px. No link has
  `aria-current`.
- **User impact:** Off-screen destinations are easy to miss, orientation is weak,
  and repeated horizontal navigation is slow on touch and keyboard.
- **Severity:** High.
- **Evidence:** `templates/base.html`;
  `firstbrief/core/static/css/app.css`; authenticated viewport audit of `/`,
  `/messages/manage/new/` and `/reports/F12/`.
- **Recommended change:** Introduce a responsive menu grouped around Briefings,
  Find, Manage, Insights/Assurance and Admin; keep Account separate; mark the
  current item and preserve server-side capability filtering.
- **Related requirements:** FR-B01, FR-G1-15, FR-H01; NFR usability and WCAG.
- **Accessibility implications:** Add `aria-current="page"`, a labelled menu
  button with expanded state, logical focus order and escape/focus restoration.
- **Implementation effort:** Medium.
- **Suggested test approach:** Template tests for role variants/current item;
  keyboard browser test; 390/768/1280 px visual and overflow checks.

### UX-02 — Implemented administration and assurance areas are not reliably reachable

- **User role:** User administrators, audit viewers and retention managers.
- **Current behaviour:** `/access/users/` is implemented but absent from global or
  configuration navigation. `/assurance/retention/` is not linked from Audit.
  Worse, a user with `MANAGE_RETENTION` but not `VIEW_AUDIT_HISTORY` receives an
  Assurance link whose target is `/assurance/`, which returns 403.
- **User impact:** Authorised work appears unavailable; retention-only users are
  sent into an error path.
- **Severity:** Critical.
- **Evidence:** `templates/base.html`; `templates/assurance/audit.html`;
  `templates/assurance/retention.html`; `firstbrief/core/context_processors.py`;
  `firstbrief/assurance/urls.py`; `firstbrief/identity/urls.py`.
- **Recommended change:** Add capability-specific section navigation; route
  Assurance to the first permitted child; expose Users under Administration.
- **Related requirements:** FR-E07, FR-G2-06; Prompt 12 assurance/retention.
- **Accessibility implications:** Predictable links reduce error recovery and
  cognitive load; section navigation needs a distinct accessible label.
- **Implementation effort:** Small.
- **Suggested test approach:** Parametrised client tests for audit-only,
  retention-only, both and neither; browser assertions for visible destinations.

### UX-03 — Tables remain technically responsive but operationally difficult on mobile

- **User role:** Readers, message managers, report users, auditors and admins.
- **Current behaviour:** Wide result sets are wrapped in horizontal scrollers.
  The mobile Search table measured 695 px inside 358 px. Sort context, row identity
  and actions can be separated by scrolling.
- **User impact:** Comparison and row actions are error-prone on phones; important
  status is hidden outside the initial viewport.
- **Severity:** High.
- **Evidence:** `templates/operations/partials/message_table.html`;
  `templates/messaging/list.html`; `templates/retrieval/search.html`;
  `templates/reporting/catalogue.html`; `templates/assurance/audit.html`;
  `firstbrief/core/static/css/app.css`.
- **Recommended change:** Define priority columns per task and render mobile cards
  or stacked rows; retain the full table above a suitable breakpoint.
- **Related requirements:** FR-B09, FR-D05, FR-E29, FR-F01–FR-F14.
- **Accessibility implications:** Preserve header relationships, row labels and a
  sensible screen-reader reading order; do not hide required data.
- **Implementation effort:** Medium–large.
- **Suggested test approach:** Responsive snapshots and keyboard/screen-reader
  checks; assert every desktop datum remains available in the mobile variant.

### UX-04 — Authoring is a single, non-adaptive form

- **User role:** BOTD originators and Instruction authors.
- **Current behaviour:** Create/revise exposes a generic 20-control form. Fields
  for type, content, dates, subtype, files, approvers and three audience-right
  lists are presented together without a staged review or live applicability
  summary.
- **User impact:** Authors must understand the entire domain model up front,
  increasing validation errors and incorrect audience selection.
- **Severity:** High.
- **Evidence:** `templates/messaging/form.html`;
  `firstbrief/messaging/forms.py`; `firstbrief/messaging/models.py`.
- **Recommended change:** Use type-aware sections (Basics, Content, Timing,
  Audience, Approval, Review), hide inapplicable controls while preserving
  server validation, and show the effective audience/rights before submission.
- **Related requirements:** FR-C01, FR-E01, FR-E02, FR-E25, FR-E26, FR-G1-14.
- **Accessibility implications:** Sections need headings and error-to-field links;
  dynamic disclosure must announce changes and never remove entered data silently.
- **Implementation effort:** Large.
- **Suggested test approach:** Form-unit matrix by message type plus browser tests
  for keyboard progression, validation focus and no-JavaScript fallback.

### UX-05 — Lifecycle actions compete and consequences are unclear

- **User role:** Authors, approvers and message managers.
- **Current behaviour:** Message detail presents several forms and free-text
  justification fields at similar prominence. Withdraw/archive/restore and
  approval actions rely mainly on button labels; permitted actions in the grid
  are plain text and require opening each record.
- **User impact:** Slow routine approvals and increased risk of selecting the
  wrong irreversible or audience-affecting transition.
- **Severity:** High.
- **Evidence:** `templates/messaging/detail.html`;
  `templates/messaging/list.html`; `firstbrief/messaging/services.py`.
- **Recommended change:** Separate primary next action from secondary and danger
  actions, state the resulting status/audience effect, require confirmation only
  for destructive transitions, and expose safe row-level actions.
- **Related requirements:** FR-C03, FR-E04–FR-E07, FR-E29.
- **Accessibility implications:** Confirmation dialogs require labelled
  descriptions, initial focus, focus return and non-colour danger indicators.
- **Implementation effort:** Medium.
- **Suggested test approach:** State/capability action matrix; browser confirmation
  tests; verify cancel is side-effect free.

### UX-06 — Every report receives an oversized generic criteria form

- **User role:** Report viewers, supervisors and compliance staff.
- **Current behaviour:** A focused report such as F12 exposes 18 controls,
  including criteria unrelated to its primary task. Required combinations and
  useful defaults are not obvious.
- **User impact:** High cognitive load, invalid runs and low confidence that a
  report reflects the intended cohort.
- **Severity:** High.
- **Evidence:** `templates/reporting/criteria.html`;
  `firstbrief/reporting/forms.py`; browser audit of `/reports/F12/`.
- **Recommended change:** Declare relevant criteria per report, prefill safe
  defaults, progressively disclose advanced fields and summarise the applied
  criteria before running.
- **Related requirements:** FR-F01–FR-F28, especially FR-F17–FR-F22 and FR-F25–28.
- **Accessibility implications:** Hidden criteria must be programmatically
  associated with their disclosure; required/help text and errors must be
  announced.
- **Implementation effort:** Medium.
- **Suggested test approach:** Per-report field allow-list tests and representative
  end-to-end runs with boundary dates/scopes.

### UX-07 — Asynchronous report and job states are not announced or recoverable enough

- **User role:** Report viewers and notification operators.
- **Current behaviour:** The report viewer uses an HTML refresh while queued or
  running, with no `aria-live` progress, cancel action or elapsed-state message.
  Failed jobs expose limited recovery guidance. Notification operations exposes
  raw technical errors and resend controls in a dense page.
- **User impact:** Users cannot tell whether work is progressing, when to wait, or
  how to recover without duplicating work.
- **Severity:** High.
- **Evidence:** `templates/reporting/viewer.html`;
  `templates/notifications/operations.html`;
  `firstbrief/reporting/views.py`; `firstbrief/notifications/views.py`.
- **Recommended change:** Use a valid polling/progress component with status,
  start time and accessible announcements; offer retry/back-to-criteria guidance;
  translate operator errors while retaining correlation details.
- **Related requirements:** FR-F01–FR-F14, FR-E03, FR-E06, FR-E27–FR-E28.
- **Accessibility implications:** WCAG 4.1.3 status messages; avoid unexpected
  refresh/focus loss and respect reduced motion.
- **Implementation effort:** Medium.
- **Suggested test approach:** Deterministic queued/running/completed/failed tests,
  fake timers and accessibility assertions for live regions.

### UX-08 — Search mixes two tasks and lacks a strong applied-filter model

- **User role:** Readers, message managers and report users.
- **Current behaviour:** Message search includes many fields plus a separate user
  lookup that does not visibly feed message results. Applied scope and a one-click
  clear/reset action are weak, while export remains prominent for empty results.
- **User impact:** Users may believe the selected user constrains message search;
  complex searches are hard to verify and amend.
- **Severity:** Medium.
- **Evidence:** `templates/retrieval/search.html`;
  `firstbrief/retrieval/forms.py`; `firstbrief/retrieval/views.py`.
- **Recommended change:** Separate user lookup from message criteria or explicitly
  connect it; add applied-filter chips/summary, clear-all and result-count-aware
  actions.
- **Related requirements:** FR-C02, FR-E08, FR-F17, FR-F18, FR-F21.
- **Accessibility implications:** Filter removal must have explicit names and
  announce updated result counts without moving focus unexpectedly.
- **Implementation effort:** Medium.
- **Suggested test approach:** Query-to-summary tests, empty/results browser tests
  and keyboard operation of filter removal.

### UX-09 — SAP review does not show enough change context

- **User role:** System administrators importing SAP data.
- **Current behaviour:** Preview/review primarily shows action and user identity.
  It does not give a clear field-level old/new comparison, affected access/report
  impact or final confirmation count. Rejected files are listed without a direct
  repair/detail journey.
- **User impact:** Administrators cannot confidently distinguish safe bulk changes
  from access-sensitive updates before commit.
- **Severity:** High.
- **Evidence:** `templates/imports/index.html`;
  `templates/imports/review.html`; `templates/imports/complete.html`;
  `firstbrief/imports/services.py`.
- **Recommended change:** Add a field diff, impact labels, group/site summaries,
  selected-update total, validation/rejection detail and a final confirm step.
- **Related requirements:** FR-G2-03, FR-F11; Prompt 10 import requirements.
- **Accessibility implications:** Do not encode add/change/remove by colour alone;
  associate checkboxes with the complete change description.
- **Implementation effort:** Medium.
- **Suggested test approach:** Fixture-based add/change/disable/reject scenarios,
  selection summary tests and commit/cancel end-to-end tests.

### UX-10 — Retention and two-person purge flow lacks discoverability and role guidance

- **User role:** Retention managers, independent approvers and auditors.
- **Current behaviour:** Retention is unlinked from Audit; active legal holds are
  counted but not listed or manageable in the UI. Purge preview exposes technical
  hashes but little candidate context. The requester sees an Approve action that
  the server will reject under the two-person rule.
- **User impact:** A high-risk compliance workflow invites dead ends and support
  work; users cannot easily verify what is held or who must act next.
- **Severity:** Critical.
- **Evidence:** `templates/assurance/retention.html`;
  `templates/assurance/purge_preview.html`;
  `firstbrief/assurance/views.py`; `firstbrief/assurance/services.py`.
- **Recommended change:** Add retention section navigation and legal-hold list;
  show candidate categories/counts and human-readable consequences; replace the
  requester's approve action with “Awaiting independent approval”.
- **Related requirements:** Prompt 12 retention, continuity and two-person
  control; FR-E07 assurance evidence.
- **Accessibility implications:** Danger/approval state must be textual, focusable
  and announced; hashes should be supplementary, not the primary explanation.
- **Implementation effort:** Medium.
- **Suggested test approach:** Requester/independent/unauthorised role browser
  matrix, active-hold fixtures and purge preview/approve/cancel tests.

### UX-11 — User administration and credential hand-off are incomplete as journeys

- **User role:** User administrators and newly provisioned users.
- **Current behaviour:** The user route is not linked, lists only a bounded set,
  and combines creation and inline password reset. Search, pagination and an
  obvious edit journey are absent from the visible surface. The one-time password
  page offers no copy/acknowledgement support or hand-off guidance.
- **User impact:** Administration does not scale and credential transfer is prone
  to transcription and process errors.
- **Severity:** High.
- **Evidence:** `templates/identity/user_list.html`;
  `templates/identity/user_form.html`;
  `templates/identity/password_reset_complete.html`;
  `firstbrief/identity/views.py`; `firstbrief/identity/urls.py`.
- **Recommended change:** Provide linked search/pagination/edit details; separate
  reset into a confirmed action; explain secure transfer and forced change, with
  a deliberate one-time copy facility.
- **Related requirements:** FR-G2-01, FR-G2-06, FR-G2-12, FR-A03.
- **Accessibility implications:** Copy status needs a live message; inline reset
  buttons need unique accessible names including the user ID.
- **Implementation effort:** Medium–large.
- **Suggested test approach:** Large user fixture, site-scope/search/pagination
  tests, reset confirmation/cancel tests and single-display password test.

### UX-12 — Configuration is a long catalogue rather than a task-oriented workspace

- **User role:** System managers and configuration administrators.
- **Current behaviour:** Eight taxonomy/settings tables are stacked on one page.
  Tree relationships are mostly visual text; there is no section index,
  search/filter or consolidated dependency warning before edits/deletes.
- **User impact:** Finding the right object becomes slow as data grows, and
  administrators lose context across repeated add/edit pages.
- **Severity:** Medium.
- **Evidence:** `templates/configuration/index.html`;
  `templates/configuration/tree.html`;
  `templates/configuration/form.html`;
  `firstbrief/configuration/urls.py`.
- **Recommended change:** Create a configuration landing/index with section
  summaries, search and linked hierarchy nodes; show dependency impact beside
  destructive actions.
- **Related requirements:** FR-G1-01–FR-G1-15, FR-G2-02, FR-G2-05, FR-G2-07.
- **Accessibility implications:** Hierarchies require proper nested lists/tree
  semantics and keyboard behaviour if an interactive tree is introduced.
- **Implementation effort:** Medium.
- **Suggested test approach:** Growing-data usability fixture, hierarchy keyboard
  test and dependency-warning view tests.

### UX-13 — Authentication/profile forms have inconsistent error and completion patterns

- **User role:** All users, including locked-out and first-login users.
- **Current behaviour:** Login is clear, but several password/recovery/profile
  templates render terse `form.as_p` layouts without the consistent error summary,
  title block or next-step guidance used elsewhere.
- **User impact:** Recovery and forced-change errors take longer to diagnose and
  successful completion destinations are inconsistent.
- **Severity:** Medium.
- **Evidence:** `templates/registration/login.html`;
  `templates/registration/password_change_form.html`;
  `templates/identity/password_reset_request.html`;
  `templates/identity/forced_password_change.html`;
  `templates/identity/profile.html`.
- **Recommended change:** Standardise an authentication form pattern with summary,
  per-field help/errors, password rules before submission and a clear completion
  action.
- **Related requirements:** FR-A01–FR-A03, FR-A09, FR-H01–FR-H05.
- **Accessibility implications:** Focus the error summary, link errors to inputs
  and expose password requirements before failure.
- **Implementation effort:** Small–medium.
- **Suggested test approach:** Template accessibility assertions and browser tests
  for invalid, locked, expired, reset and success paths.

### UX-14 — Reader state and PDF fallback are not sufficiently communicated

- **User role:** Operational message readers.
- **Current behaviour:** The viewer presents the message and actions well, but
  active reading-time capture is silent; there is no visible paused/active state
  or save indication. PDF content relies on an embedded viewer with limited
  mobile fallback guidance.
- **User impact:** Readers cannot tell whether their access/read evidence is being
  captured, and mobile PDF users may struggle to zoom or open externally.
- **Severity:** Medium.
- **Evidence:** `templates/operations/message_viewer.html`;
  `firstbrief/core/static/js/consumption.js`;
  `firstbrief/operations/views.py`.
- **Recommended change:** Add a restrained read-session state and accessible PDF
  open/download fallback; keep the message title and close/ack action reachable
  on long content.
- **Related requirements:** FR-D01–FR-D04, FR-F27.
- **Accessibility implications:** Status changes require non-intrusive live
  announcements; iframe needs a useful title and equivalent link.
- **Implementation effort:** Medium.
- **Suggested test approach:** Visibility/idle timer tests, mobile PDF fixture,
  keyboard action reachability and live-region assertions.

### UX-15 — Empty, success and error states are not consistently actionable

- **User role:** All roles.
- **Current behaviour:** Dashboard and list empty states are generally clear, but
  some administrative/report/import states are plain text without a permitted
  next action. Raw job/import errors can leak implementation language. Django
  success messages are present but not always tied to the object or next task.
- **User impact:** Users reach valid dead ends and depend on support to recover.
- **Severity:** Medium.
- **Evidence:** `templates/reporting/viewer.html`;
  `templates/imports/index.html`; `templates/notifications/operations.html`;
  `templates/assurance/audit.html`; `templates/base.html`.
- **Recommended change:** Adopt a state pattern: what happened, impact, permitted
  next action, correlation/detail for support; disable result-only actions when
  there is no result.
- **Related requirements:** Cross-cutting FR-A–FR-H; NFR operability/usability.
- **Accessibility implications:** Success/error containers need roles/live-region
  behaviour without repeated announcements after navigation.
- **Implementation effort:** Small–medium.
- **Suggested test approach:** State inventory snapshots and assertions for an
  accessible heading, explanation and next action in each state.

## Safe defect corrected during the audit

`templates/operations/print_message.html` contained an inline script even though
the production Content Security Policy allows only same-origin scripts. The print
trigger is now a data attribute handled by the existing same-origin
`firstbrief/core/static/js/app.js`. A regression test in
`tests/test_release_hardening.py` verifies that the print template contains no
inline script. This is a small compatibility/accessibility defect fix, not a
redesign.

## Release-gate result

See the final section of `docs/ux-backlog.md` for the recorded command outcomes.

