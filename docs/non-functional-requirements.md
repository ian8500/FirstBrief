# Non-functional requirements

These are proposed acceptance requirements derived from material gaps in the controlling source. Numeric placeholders must be approved during discovery.

| ID | Requirement | Measurable acceptance |
|---|---|---|
| NFR-01 | Availability and recovery | Approved service hours/availability, RTO, RPO, backup frequency, and restore cadence are configured and demonstrated in staging. |
| NFR-02 | Performance | At agreed concurrent-user/data volume, p95 dashboard and list responses are under 2 seconds; large reports run asynchronously within an approved completion target. |
| NFR-03 | Accessibility | Core journeys meet WCAG 2.2 AA through automated checks and documented keyboard/screen-reader/manual evidence. |
| NFR-04 | Security | Controls align to approved OWASP ASVS level; SSO/MFA is preferred; critical/high findings are resolved or formally excepted. |
| NFR-05 | Audit | Defined security, lifecycle, access, acknowledgement, export, import, and configuration events are append-only, searchable by authorised users, and protected from application-role mutation. |
| NFR-06 | Time | UTC is authoritative; display uses configured IANA site timezone; DST gap/fold and late/duplicate job behaviour have deterministic tests. |
| NFR-07 | Concurrency | Stale updates cannot silently overwrite newer data; users receive a compare/refresh conflict response. |
| NFR-08 | File assurance | Approved size/type limits, PDF integrity, malware scan, checksum, versioning, quarantine, and authorised retrieval are enforced. |
| NFR-09 | Data protection | Classification, minimisation, retention, legal hold, subject-access/export/redaction, and purge evidence follow approved policy. |
| NFR-10 | Operational resilience | Health/readiness checks, queue/outbox monitoring, retries, dead-letter visibility, alerting, and degraded-mode messaging are exercised. |

## Cross-cutting release targets to approve

- Supported browsers/devices and responsive breakpoints.
- Load model, dataset sizes, report/export quotas, and job completion targets.
- Service hours, availability percentage, RTO/RPO, backup/restore frequency.
- Log, audit, message, file, report, and import retention periods.
- Email delivery objectives, quiet hours, retry window, and dead-letter response.
- Security classification, encryption/key management, vulnerability remediation windows.
- Accessibility test environments and named manual-assurance owner.

