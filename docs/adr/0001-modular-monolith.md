# ADR 0001: Modular Django monolith

- Status: Accepted for implementation
- Date: 2026-07-23

## Decision

Use Python 3.12 and an approved Django 5 LTS-compatible release as a modular monolith. Use server-rendered templates with progressive enhancement and bounded DRF APIs. Domain services and module ownership are explicit.

## Consequences

Transactions, deployment, assurance, and reporting joins remain straightforward. Module boundaries must be enforced by conventions/tests because they are not network boundaries. Microservices are not justified by the current scale or team evidence.

