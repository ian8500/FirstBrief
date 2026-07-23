# FirstBrief

FirstBrief is being developed as a secure, auditable operational briefing application.

The repository currently contains the completed Prompt 0 design gate, Prompt 1
engineering foundation, and Prompt 2 identity/access gate:

- 121 source requirements inventoried and mapped to bounded components;
- 17 proposed gap-closing requirements kept separately from the controlling source;
- solution, domain, lifecycle, threat, and non-functional designs;
- architecture decisions for identity, audit, files, background work, and reporting;
- a prioritised Prompt 1–12 delivery backlog.
- Django 5.2 LTS with PostgreSQL, Redis, and Celery;
- secure environment-based settings, correlation-aware JSON logs, and health checks;
- container development, CI, formatting, typing, tests, and dependency auditing.
- users, roles, granular capabilities, site/group scope and message-type access;
- Argon2 local fallback, lockout, forced change, reset links and audit evidence.

Start with [the Prompt 2 verification report](docs/prompt-2-verification.md),
[developer setup](docs/development.md), and [solution design](docs/solution-design.md).

## Run locally

```bash
docker compose up --build
```

Open `http://localhost:8001/`. See [developer setup](docs/development.md) for
native Python setup, test commands, and seed data.

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
