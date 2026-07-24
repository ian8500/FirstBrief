# SAP import contract — version 1

Files are UTF-8 CSV, no larger than 2 MB, with this exact header:

```text
schema_version,action,user_id,first_name,last_name,email,site_code,group_codes,include_in_reports
```

`schema_version` is `1`; `action` is `upsert` or `deactivate`; group codes are
pipe-separated and must belong to the named site. Identity is the immutable
`user_id`. Duplicate identities, unknown/cross-site references, binary/NUL
content, invalid UTF-8, malformed CSV and unknown schema versions are rejected.

The preview stores canonical content and SHA-256 evidence. Commit locks the batch,
re-parses that exact content, reconciles it with preview rows, and applies only
selected rows in one transaction. Imported accounts cannot use local passwords.
Each applied row feeds the F11 report contract.

This safe contract requires formal agreement with the SAP data owner before
production integration.
