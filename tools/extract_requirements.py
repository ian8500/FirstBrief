#!/usr/bin/env python3
"""Extract the authoritative detailed FirstBrief requirements from the source PDF."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

REQUIREMENT_ID = re.compile(r"(?m)^FR-(?:[A-Z]\d-\d{2}|[A-Z]\d{2})\s*$")
DETAIL_PAGES = (*range(7, 31), *range(36, 53))
SUPPLEMENTAL = {
    **{f"NFR-{number:02d}": "Cross-cutting non-functional requirement" for number in range(1, 11)},
    "FR-K01": "Instructions and lifecycle",
    "FR-K02": "Instructions and lifecycle",
    "FR-K03": "Instructions and lifecycle",
    "FR-K04": "Scheduling and notifications",
    "FR-K05": "Retention and assurance",
    "FR-K06": "Identity and access",
    "FR-K07": "Reporting and compliance",
}


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    theme: str
    role: str
    need: str
    outcome: str
    dependencies: str
    requirement_owner: str
    source_reference: str
    acceptance_criteria: str
    source_pages: str


def normalise(value: str) -> str:
    value = value.replace("\u2011", "-").replace("\u00a0", " ")
    value = re.sub(r"\[\[SOURCE_PAGE:\d+]]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def strip_page_furniture(value: str) -> str:
    return re.sub(r"(?m)^\s*NATS Internal\s*$", "", value)


def field(block: str, start: str, end: str) -> str:
    match = re.search(re.escape(start) + r"\s*(.*?)\s*" + re.escape(end), block, re.S)
    return normalise(match.group(1)) if match else ""


def parse_story(block: str) -> tuple[str, str, str]:
    match = re.search(
        r"As a\s+(.*?),\s+I need\s+(.*?),\s+so\s+that\s+(.*?)\s+Requirement Owner",
        block,
        re.S,
    )
    if not match:
        return "", "", ""
    return tuple(normalise(part) for part in match.groups())  # type: ignore[return-value]


def parse_pdf(pdf_path: Path) -> tuple[list[Requirement], int]:
    reader = PdfReader(str(pdf_path))
    pages = {
        page_number: strip_page_furniture(reader.pages[page_number - 1].extract_text() or "")
        for page_number in DETAIL_PAGES
    }

    chunks: list[str] = []
    positions: list[tuple[int, int]] = []
    cursor = 0
    for page_number in DETAIL_PAGES:
        marker = f"\n[[SOURCE_PAGE:{page_number}]]\n"
        text = marker + pages[page_number]
        chunks.append(text)
        positions.append((cursor, page_number))
        cursor += len(text)
    combined = "".join(chunks)

    starts = list(REQUIREMENT_ID.finditer(combined))
    requirements: list[Requirement] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(combined)
        block = combined[match.start() : end]
        requirement_id = match.group(0).strip()
        pages_in_block = [int(value) for value in re.findall(r"\[\[SOURCE_PAGE:(\d+)]]", block)]
        start_page = max(page for position, page in positions if position <= match.start())
        source_pages = sorted(set([start_page, *pages_in_block]))

        theme = field(block, "Theme:", "Dependencies:")
        dependencies = field(block, "Dependencies:", "As a")
        role, need, outcome = parse_story(block)
        owner = field(block, "Requirement Owner", "Source")
        source = field(block, "Source", "Acceptance Criteria:")
        criteria_text = (
            block.split("Acceptance Criteria:", 1)[1] if "Acceptance Criteria:" in block else ""
        )
        criteria_text = re.sub(r"\[\[SOURCE_PAGE:\d+]]", "", criteria_text)
        criteria = normalise(criteria_text)

        requirements.append(
            Requirement(
                requirement_id=requirement_id,
                theme=theme,
                role=role,
                need=need,
                outcome=outcome,
                dependencies=dependencies,
                requirement_owner=owner,
                source_reference=source,
                acceptance_criteria=criteria,
                source_pages=";".join(str(page) for page in source_pages),
            )
        )

    return requirements, len(reader.pages)


def write_register(requirements: list[Requirement], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(Requirement.__annotations__),
            lineterminator="\r\n",
        )
        writer.writeheader()
        for requirement in requirements:
            writer.writerow(requirement.__dict__)


def write_traceability(requirements: list[Requirement], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "requirement_id",
        "theme",
        "source_pages",
        "source_reference",
        "design_component",
        "code_path",
        "automated_test",
        "manual_test",
        "status",
        "notes",
    ]
    existing: dict[str, dict[str, str]] = {}
    if output.exists():
        with output.open(encoding="utf-8", newline="") as handle:
            existing = {
                row["requirement_id"]: row
                for row in csv.DictReader(handle)
                if row.get("requirement_id")
            }

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        for requirement in requirements:
            design_component = component_for(requirement.requirement_id)
            writer.writerow(
                preserve_evidence(
                    {
                        "requirement_id": requirement.requirement_id,
                        "theme": requirement.theme,
                        "source_pages": requirement.source_pages,
                        "source_reference": requirement.source_reference,
                        "design_component": design_component,
                        "code_path": "",
                        "automated_test": "",
                        "manual_test": "",
                        "status": "Designed",
                        "notes": (
                            "Source inventoried and allocated to a bounded module; "
                            "implementation evidence is added by subsequent prompts."
                        ),
                    },
                    existing,
                )
            )
        for requirement_id, design_component in SUPPLEMENTAL.items():
            writer.writerow(
                preserve_evidence(
                    {
                        "requirement_id": requirement_id,
                        "theme": "Proposed requirement",
                        "source_pages": "Implementation guide",
                        "source_reference": "FirstBrief Codex Implementation Blueprint",
                        "design_component": design_component,
                        "code_path": "",
                        "automated_test": "",
                        "manual_test": "",
                        "status": "Proposed",
                        "notes": (
                            "Gap-closing requirement pending formal "
                            "product/security/records approval."
                        ),
                    },
                    existing,
                )
            )


def preserve_evidence(
    default_row: dict[str, str],
    existing: dict[str, dict[str, str]],
) -> dict[str, str]:
    previous = existing.get(default_row["requirement_id"])
    if previous is None:
        return default_row

    for field_name in (
        "design_component",
        "code_path",
        "automated_test",
        "manual_test",
        "status",
        "notes",
    ):
        if previous.get(field_name):
            default_row[field_name] = previous[field_name]
    return default_row


def component_for(requirement_id: str) -> str:
    if requirement_id.startswith("FR-A"):
        return "Identity and access"
    if requirement_id.startswith("FR-B"):
        return "Operational dashboard"
    if requirement_id.startswith("FR-C"):
        return "Briefs of the Day"
    if requirement_id.startswith("FR-D"):
        return "Message consumption"
    if requirement_id.startswith("FR-E"):
        return "Instructions and lifecycle"
    if requirement_id.startswith("FR-F"):
        return "Reporting and compliance"
    if requirement_id.startswith("FR-G1"):
        return "Configuration taxonomy"
    if requirement_id in {
        "FR-G2-03",
        "FR-G2-22",
        "FR-G2-23",
        "FR-G2-24",
        "FR-G2-25",
        "FR-G2-26",
    }:
        return "SAP import"
    if requirement_id in {"FR-G2-14", "FR-G2-15", "FR-G2-16"}:
        return "Scheduling and notifications"
    if requirement_id in {"FR-G2-20", "FR-G2-21"}:
        return "Retention and assurance"
    if requirement_id.startswith("FR-G2"):
        return "Administration and access configuration"
    if requirement_id.startswith("FR-H"):
        return "User self-service"
    if requirement_id.startswith("FR-I"):
        return "Site scoping and authorisation"
    if requirement_id.startswith("FR-J"):
        return "Accessible UI platform"
    raise ValueError(f"No component mapping for {requirement_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--register", required=True, type=Path)
    parser.add_argument("--traceability", required=True, type=Path)
    args = parser.parse_args()

    requirements, page_count = parse_pdf(args.pdf)
    ids = [requirement.requirement_id for requirement in requirements]
    incomplete = [
        requirement.requirement_id
        for requirement in requirements
        if not all(
            (
                requirement.theme,
                requirement.role,
                requirement.need,
                requirement.outcome,
                requirement.source_reference,
                requirement.acceptance_criteria,
            )
        )
    ]
    if page_count != 52:
        raise SystemExit(f"Expected 52 pages, found {page_count}")
    if len(ids) != 121 or len(set(ids)) != 121:
        raise SystemExit(f"Expected 121 unique detailed requirements, found {len(set(ids))}")
    if incomplete:
        raise SystemExit(f"Incomplete parsed fields: {', '.join(incomplete)}")

    write_register(requirements, args.register)
    write_traceability(requirements, args.traceability)
    digest = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    print(f"pages={page_count}")
    print(f"requirements={len(requirements)}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
