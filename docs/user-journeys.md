# FirstBrief user journeys

This document maps the journeys that exist today. “Opportunity” describes audit
recommendations; it does not imply the underlying capability is absent.

## Roles

| Role | Primary goal | Typical capability |
|---|---|---|
| Operational reader | Find, understand and acknowledge applicable briefings | Authenticated, audience-scoped |
| Originator | Create and revise BOTD or Instruction content | `CREATE_MESSAGES` |
| Approver | Validate and approve controlled content | `APPROVE_MESSAGES` |
| Message manager | Maintain lifecycle and operational delivery | `MANAGE_MESSAGES` |
| Report viewer/supervisor | Evidence reach, activity and compliance | `VIEW_REPORTS` |
| SAP administrator | Preview and commit directory changes | `MANAGE_SAP_IMPORTS` |
| Auditor | Inspect immutable activity evidence | `VIEW_AUDIT_HISTORY` |
| Retention manager/approver | Manage holds and two-person purge | `MANAGE_RETENTION` |
| Configuration/user administrator | Maintain taxonomy, roles, users and policy | `MANAGE_CONFIGURATION`, `MANAGE_USERS` |

## J01 — Read and acknowledge a mandatory message

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Sign in | Login redirects to the operational dashboard | Recovery patterns differ from the main form pattern | Standardise recovery/error guidance (UX-13) |
| Prioritise | Dashboard shows unread mandatory, forthcoming and BOTD | Long role navigation crowds the task on small screens | Responsive role navigation (UX-01) |
| Select | Mandatory list supplies status, timing and sorting | Mobile table requires horizontal scrolling | Mobile priority-row/card view (UX-03) |
| Read | Full-width viewer shows content and metadata | Read-time state is silent; PDF fallback is limited | Reader state and accessible PDF fallback (UX-14) |
| Complete | Read & Clear/Confirm and close records evidence | Long content can separate action from context | Keep summary/completion action reachable |

Evidence: `templates/operations/dashboard.html`,
`templates/operations/message_list.html`,
`templates/operations/message_viewer.html`; FR-B01–B09, FR-D01–D06.

## J02 — Create or revise a briefing

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Enter management | Messages opens maintenance grid | Permitted actions are text, not direct task affordances | Safe row actions and clearer next action (UX-05) |
| Choose create | Create Message opens the generic form | Type choice does not first frame the rest of the workflow | Type-aware staged authoring (UX-04) |
| Define audience | Three rights lists support prohibited/allowed/mandatory | Effective reach is hard to review | Audience summary and conflict explanation |
| Add approval/content | Approvers, dates, text/files coexist in one long form | Inapplicable fields and errors raise cognitive load | Progressive sections with field dependencies |
| Submit/revise | Server validation and lifecycle evidence are strong | No final review of audience/timing/content | Review step before save |

Evidence: `templates/messaging/list.html`, `templates/messaging/form.html`,
`firstbrief/messaging/forms.py`; FR-C01, FR-E01–E03, FR-E25–E30.

## J03 — Approve and manage lifecycle

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Find work | Maintenance filters by group, subtype and status | Applied filters and actionable rows are weak | Work queue presets and filter summary |
| Inspect | Detail shows message, version and history when permitted | Many lifecycle forms compete visually | Primary-next-action hierarchy (UX-05) |
| Decide | Approval/withdraw/archive/restore use domain validation | Consequences are not explained at action point | Action-specific outcome and confirmation |
| Confirm | Messages and audit events record outcome | Success does not always suggest the next queue item | Return-to-queue / next-item affordance |

Evidence: `templates/messaging/detail.html`,
`firstbrief/messaging/services.py`; FR-E04–E07, FR-E22–E24, FR-E29.

## J04 — Find a message or user

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Open Search | Combined message criteria are scope-safe | Twenty controls make the starting point dense | Basic/advanced criteria split |
| Find user | A separate lookup is shown | Relationship to message results is unclear | Separate task or explicit user filter (UX-08) |
| Review | Results support sorting and export | Mobile result columns overflow; applied scope is weak | Filter summary and mobile priority view |
| Refine | Query values persist | No strong clear-all/change-one model | Removable filter summary |

Evidence: `templates/retrieval/search.html`; FR-C02, FR-E08,
FR-F17–F18, FR-F21.

## J05 — Run and use a report

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Select | Catalogue lists F01–F14 with descriptions | Long catalogue has limited grouping by user goal | Group by access, message, import and team |
| Define | Generic criteria form supports broad report engine | Even F12 exposes 18 controls | Per-report criteria contract (UX-06) |
| Run | Snapshot job protects consistency | Refresh state is silent and not cancellable | Accessible progress/recovery (UX-07) |
| Consume | Viewer offers PDF/CSV/print/close | Failure and zero-row recovery are terse | Explain result scope and next action |

Evidence: `templates/reporting/catalogue.html`,
`templates/reporting/criteria.html`, `templates/reporting/viewer.html`;
FR-F01–F28.

## J06 — Import SAP changes

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Select/upload | Landing explains import and lists recent files | Rejected item detail is not a clear journey | Link to structured rejection detail |
| Validate | Server parses and classifies changes | User-facing validation can be overly technical | Plain-language problem and correction |
| Review | Administrator selects proposed updates | No field-level before/after or access impact | Diff and impact review (UX-09) |
| Commit | Selected updates are applied and audited | Final selection count/consequence is weak | Confirm selected count and sites |
| Evidence | Completion summarises result; F11 exists | Link to associated report/evidence is weak | Direct F11/run evidence link |

Evidence: `templates/imports/`; `firstbrief/imports/services.py`;
FR-G2-03, FR-F11.

## J07 — Audit, hold and purge retained data

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Enter Assurance | Header points to Audit | Retention-only user is routed to a forbidden page | Capability-aware section entry (UX-02) |
| Investigate | Audit table filters action/object | Actor, site, dates and event detail are limited | Expanded assurance filters/detail |
| Review retention | Policy, continuity and hold count are shown | Active holds are not visible/manageable | Legal-hold inventory (UX-10) |
| Request purge | Preview/evidence hash protects integrity | Candidate impact is technical | Human-readable candidate summary |
| Approve | Independent approver is enforced server-side | Requester still sees an action that will fail | Explicit awaiting-independent-approval state |

Evidence: `templates/assurance/`; `firstbrief/assurance/services.py`;
Prompt 12 controls, FR-E07.

## J08 — Maintain configuration and users

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Navigate | Configuration exposes all configured domains | Users is not linked; page stacks eight tables | Admin IA and section index (UX-02, UX-12) |
| Find object | Lists/tree show configured values | Little search and some hierarchy is non-interactive | Search and linked hierarchy |
| Edit | Forms validate dependencies and scope | Context is lost across generic add/edit screens | Breadcrumb and dependency summary |
| Provision user | Create/reset flows exist | No scalable list/search/edit journey | Complete user admin workspace (UX-11) |
| Handoff | One-time credential is shown | Secure handoff and copy confirmation are weak | One-time copy acknowledgement |

Evidence: `templates/configuration/`, `templates/identity/user_*`;
FR-G1-01–G1-15, FR-G2-01–G2-14.

## J09 — Maintain personal access and preferences

| Stage | Current journey | Friction / risk | Opportunity |
|---|---|---|---|
| Profile | Read-only identity, groups and roles are visible | Related actions are not grouped consistently | Account hub |
| Display | User can set display preferences | Link competes in the global operational nav | Move under Account with optional quick access |
| Password | Change/forced-change/reset are supported | Form help/error/success patterns vary | Shared authentication form pattern (UX-13) |
| Feedback/help | Feedback and guide capabilities exist | Entry points vary by page/context | Consistent Help destination |

Evidence: `templates/identity/`, `templates/registration/`,
`templates/operations/display_settings.html`; FR-H01–H05, FR-A01–A09.

## Cross-journey state expectations

Every journey should use the same state contract:

1. **Loading:** name the operation, retain context, announce meaningful progress.
2. **Empty:** explain why no data is present and show a permitted next action.
3. **Error:** describe what failed in user language, preserve entered criteria, and
   supply a retry/back action plus correlation detail where appropriate.
4. **Success:** state the object and resulting status, then offer the next likely
   task.
5. **Permission denied:** explain the unavailable capability without exposing
   protected data, and return to the nearest valid section.

