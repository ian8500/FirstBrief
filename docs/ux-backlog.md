# FirstBrief UX backlog

## Prioritisation

Priority combines user harm, frequency, reach, compliance/safety exposure and
implementation effort. Severity uses Critical, High, Medium and Low. Detailed
evidence and test approaches are in `docs/ux-audit.md`.

## Top ten

| Rank | Item | Value | Severity | Effort | Requirement IDs | Primary test |
|---:|---|---|---|---|---|---|
| 1 | UX-01 Responsive role-aware navigation and current state | All users can find and orient to work | High | M | FR-B01, FR-G1-15, FR-H01 | Role × viewport browser matrix |
| 2 | UX-02 Fix Assurance entry; link Retention and Users | Removes authorised-user dead ends/403 | Critical | S | FR-E07, FR-G2-06 | Capability route/navigation matrix |
| 3 | UX-06 Per-report criteria | Fewer invalid runs, higher evidence confidence | High | M | FR-F01–F28 | Per-code field contract |
| 4 | UX-04 Type-aware staged authoring | Reduces audience/content errors | High | L | FR-C01, FR-E01–E03, E25–E26 | Type/audience E2E matrix |
| 5 | UX-05 Lifecycle action hierarchy | Reduces high-impact transition errors | High | M | FR-C03, FR-E04–E07, E29 | State/capability action matrix |
| 6 | UX-10 Retention/hold/approval journey | Makes two-person control operable | Critical | M | Prompt 12, FR-E07 | Requester/approver role tests |
| 7 | UX-03 Mobile task views for tables | Makes core work usable on phones | High | M–L | FR-B09, D05, E29, F01–F14 | Responsive content-equivalence tests |
| 8 | UX-09 SAP before/after impact review | Safer bulk identity/access change | High | M | FR-G2-03, FR-F11 | Import fixture and commit/cancel E2E |
| 9 | UX-07 Accessible async/recovery states | Prevents duplicate/abandoned jobs | High | M | FR-F01–F14, E03, E06 | Job-state/live-region tests |
| 10 | UX-11 Scalable user admin and credential hand-off | Supports real administration volumes | High | M–L | FR-G2-01, G2-06, A03 | Search/page/edit/reset E2E |

## Delivery sequence

### Now — correctness and navigation

1. **UX-02:** correct the Assurance target by capability; add Assurance child
   navigation and a Users link.
2. **UX-01 phase 1:** add current-location semantics and group labels without
   changing routes.
3. **UX-13:** standardise authentication error summaries and completion actions.
4. **UX-15:** adopt the actionable empty/error/success state pattern.
5. **UX-10 phase 1:** hide requester approval, explain independent approval, list
   active legal holds read-only.

### Next — reduce errors in high-value workflows

6. **UX-06:** introduce a declarative field set for each F01–F14 report and an
   applied-criteria summary.
7. **UX-05:** define primary/secondary/danger lifecycle actions with consequence
   text and selective confirmation.
8. **UX-09:** add SAP field diffs, impact labels and confirmation totals.
9. **UX-07:** replace refresh-only job status with accessible polling/status and
   recovery.
10. **UX-08:** separate user lookup or connect it explicitly to message criteria.

### Later — structural workflow improvements

11. **UX-01 phase 2:** responsive grouped navigation.
12. **UX-03:** reusable mobile row/card component, starting with Mandatory,
    maintenance and Search.
13. **UX-04:** staged, type-aware authoring and final review.
14. **UX-11:** user search, pagination, edit and safer reset workflow.
15. **UX-12:** task-oriented configuration hub and searchable hierarchy.
16. **UX-14:** reader session status, sticky completion and PDF fallback.

## Definition of done for UX backlog items

- Existing permission, scope, state-machine and audit controls remain enforced.
- Requirement traceability and README/user guide are updated with the change.
- Keyboard-only completion is demonstrated.
- Labels, names, roles, values, focus and status announcements are tested.
- Empty, loading, validation, error, success and permission-denied variants are
  covered where applicable.
- 390 px, 768 px and 1280 px layouts have no page-level overflow; deliberate data
  overflow has an equivalent task-oriented presentation.
- Automated tests include both allowed and denied role/scope variants.
- The release gate passes.

## Release-gate record

The authoritative gate is `docs/release-candidate.md`:

```text
ruff check .
mypy firstbrief tests
python manage.py makemigrations --check --dry-run
python manage.py check --deploy --settings=firstbrief.settings.production
pytest --cov=firstbrief --cov-fail-under=80
pip-audit --requirement requirements/base.txt
python manage.py release_evidence
```

Results from 24 July 2026:

| Gate | Result | Evidence |
|---|---|---|
| `ruff check .` | Pass | All checks passed |
| `mypy firstbrief tests` | Pass | No issues in 120 source files |
| `makemigrations --check --dry-run` | Pass | No changes detected |
| production `check --deploy` | Pass | No issues (production-like non-secret environment values) |
| `pytest --cov=firstbrief --cov-fail-under=80` | Pass | 120 passed, 4 skipped; 85.16% |
| `pip-audit --requirement requirements/base.txt` | Inconclusive | Dependency-isolation bootstrap produced no output for three minutes and was interrupted |
| top-level pinned audit (`--disable-pip --no-deps`) | Pass, supplementary | No known vulnerabilities in the 11 direct pinned requirements |
| current audit environment (`pip-audit --local`) | Fail, environment-only | Five advisories affect tooling package `pip 25.0.1`; fixed by upgrading pip to at least 26.1.2. `pip` is not in `requirements/base.txt` or the runtime image dependency list |
| `python manage.py release_evidence` | Pass | `release_evidence=ready`; 1 message, 5 audit events, 1 report run, no imports/holds/purges in the local audit database |

The release gate is therefore **not fully green**: application checks and the
supplementary direct-dependency audit pass, but the exact isolated dependency
audit did not complete in the available environment. Re-run that exact command
in CI or an environment where Python virtual-environment bootstrap completes;
do not treat the supplementary `--no-deps` result as equivalent coverage of
transitive dependencies.
