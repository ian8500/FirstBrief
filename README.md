# FirstBrief

FirstBrief is being developed as a secure, auditable operational briefing application.

The repository currently contains the completed Prompt 0 design gate:

- 121 source requirements inventoried and mapped to bounded components;
- 17 proposed gap-closing requirements kept separately from the controlling source;
- solution, domain, lifecycle, threat, and non-functional designs;
- architecture decisions for identity, audit, files, background work, and reporting;
- a prioritised Prompt 1–12 delivery backlog.

Start with [the Prompt 0 verification report](docs/prompt-0-verification.md) and
[solution design](docs/solution-design.md).

## Controlled source

The controlling requirements PDF is marked **Internal** and is intentionally
excluded from Git. Place an authorised copy at:

`docs/source/FirstBrief_Master_Requirements_TwoSections.pdf`

Then regenerate and verify the registers:

```bash
python tools/extract_requirements.py \
  docs/source/FirstBrief_Master_Requirements_TwoSections.pdf \
  --register docs/requirements/requirements-register.csv \
  --traceability docs/requirements-traceability.csv

python -m unittest discover -s tests -v
```

Do not publish controlled source material without the required
information-classification approval.
