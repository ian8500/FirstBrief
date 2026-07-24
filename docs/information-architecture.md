# FirstBrief information architecture

## Current route and capability map

```text
FirstBrief
├── Dashboard (/)
├── Briefing consumption
│   ├── Mandatory (/operational/mandatory/)
│   ├── Other messages (/operational/other/)
│   └── Message reader (/operational/messages/<id>/)
├── Search (/search/)
├── Message management [CREATE/APPROVE/MANAGE_MESSAGES]
│   ├── Maintenance (/messages/manage/)
│   ├── Create (/messages/manage/new/)
│   └── Detail/lifecycle (/messages/manage/<id>/)
├── Reports [VIEW_REPORTS]
│   ├── Catalogue (/reports/)
│   ├── Criteria (/reports/<code>/)
│   └── Viewer (/reports/runs/<id>/)
├── SAP import [MANAGE_SAP_IMPORTS]
│   ├── Import list/upload (/imports/)
│   ├── Review (/imports/<id>/review/)
│   └── Complete (/imports/<id>/complete/)
├── Assurance
│   ├── Audit [VIEW_AUDIT_HISTORY] (/assurance/)
│   └── Retention [MANAGE_RETENTION] (/assurance/retention/)
├── Administration
│   ├── Configuration [MANAGE_CONFIGURATION] (/configuration/)
│   ├── Notifications [configuration/notification capability]
│   └── Users [MANAGE_USERS] (/access/users/) — not linked
└── Account
    ├── Profile (/access/profile/)
    ├── Display settings (/operational/settings/)
    ├── Password change/recovery
    └── Log out
```

Routes are defined in `firstbrief/urls.py` and each application `urls.py`.
Visibility is composed in `firstbrief/core/context_processors.py` and
`templates/base.html`; views remain the authoritative permission boundary.

## Domain information model

```text
User ── membership/role ──> Message Group / Primary Message Group
  │                              │
  ├── reportees                  ├── subtype / sector / distribution
  ├── access & receipt evidence  └── audience right
  └── capabilities                         │
                                           v
Message ── immutable identity ──> Message Version ── lifecycle/approval
  │                                      │
  ├── viewer sessions/feedback           ├── display/print assets
  ├── notification jobs                  └── timing/content/audience
  └── audit events / report snapshots / retention evidence

SAP import ── proposed changes ──> User/group data ──> F11 evidence
Retention policy + legal holds ──> purge preview ──> independent approval
```

This underlying model is strong, but the visible IA currently mirrors subsystems
more than user goals.

## IA findings

1. **The header is a permission-filtered route list, not a hierarchy.** An
   administrator sees up to thirteen peers. It overflows at tablet and mobile
   widths and gives no current location.
2. **Assurance has an invalid default for retention-only users.**
   `can_view_assurance` includes either assurance capability, but the header
   always targets the audit-only route.
3. **Users is an orphan destination.** It exists under the identity URL namespace
   but is absent from Administration/Configuration navigation.
4. **Configuration is both a destination and an index of eight domains.** Its
   scale is hidden until entry and there is no persistent section navigation.
5. **Display settings is promoted to global operational navigation although it
   belongs conceptually to Account.**
6. **Reports are organised by report code.** Codes are valid organisational
   identifiers but do not explain user goal without reading every description.
7. **Search contains both message search and user lookup**, mixing two information
   objects without making their relationship explicit.

## Recommended target IA

Keep URLs stable initially; change labels/grouping before route structure.

```text
Primary
├── Briefings
│   ├── Dashboard
│   ├── Mandatory
│   └── Other messages
├── Find
│   └── Message search
├── Manage (only when authorised)
│   ├── Work queue / Messages
│   ├── Create message
│   └── Notification operations
├── Insights & assurance (only when authorised)
│   ├── Reports
│   │   ├── Access & reach
│   │   ├── Message lifecycle
│   │   ├── Imports
│   │   └── Team activity
│   ├── Audit history
│   └── Retention & continuity
└── Administration (only when authorised)
    ├── Users
    ├── Roles & identity
    ├── Message taxonomy
    ├── Sites, groups & sectors
    ├── Distributions & policy
    └── SAP imports

Utility / account
├── Profile
├── Display settings
├── Change password
├── Help / user guide / feedback
└── Log out
```

## Navigation rules

- Determine the first permitted child for grouped destinations; never link a user
  to a known 403.
- Keep view-level capability checks authoritative. Navigation is discovery, not
  access control.
- Render only relevant groups and children, but keep their ordering stable.
- Apply `aria-current="page"` to the most specific current item and use a
  separately labelled section/breadcrumb navigation below the global header.
- On small screens use one labelled menu control; avoid a hidden horizontal
  scroll as the only way to discover destinations.
- Preserve deep links and return URLs through authentication.
- Provide a landing page only where a group has three or more substantive tasks;
  otherwise route to the first permitted child.

## Naming and wayfinding

- Use task language first and retain codes second: “Message access cohort (F12)”.
- Use “Manage messages” for the work queue and “Create message” for authoring.
- Use “Audit history” and “Retention & continuity” as Assurance children.
- Use a consistent breadcrumb for detail/edit/review screens:
  `Manage messages › <message ID> › <action>`.
- Display current PMG/site scope wherever a list, report or import is scoped; scope
  is part of location, not merely an implementation detail.

